"""Safe SDK failure metadata, with real SDK exceptions and offline HTTP transport."""
from copy import deepcopy
import json
import os

import anthropic
import httpx
import pytest

from copilot import budget as budget_module
from copilot.budget import Budget, Limits, guard_sdk

BODY = {"model": "claude-haiku-5-5", "max_tokens": 4096,
        "thinking": {"type": "adaptive"}, "output_config": {"effort": "low"},
        "messages": [{"role": "user", "content": "PRIVATE_INPUT_FIXTURE"}]}
SECRET = "sk-ant-api03-NEVER_PERSIST_THIS_FIXTURE"
PRIVATE = "PRIVATE_RESPONSE_FIXTURE"


def recorder(path):
    def persist(snapshot):
        with path.open("a") as stream:
            stream.write(json.dumps(snapshot) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    return persist


@pytest.mark.parametrize("status,error_type,exception_type", [
    (400, "invalid_request_error", "BadRequestError"),
    (401, "authentication_error", "AuthenticationError"),
    (403, "permission_error", "PermissionDeniedError"),
    (429, "rate_limit_error", "RateLimitError"),
    (500, "api_error", "InternalServerError"),
    (503, "service_unavailable_error", "ServiceUnavailableError"),
    (504, "deadline_exceeded_error", "DeadlineExceededError"),
    (529, "overloaded_error", "OverloadedError"),
])
def test_http_failure_persists_only_safe_metadata_before_propagating(
        tmp_path, status, error_type, exception_type):
    sent = []
    def reply(request):
        sent.append(request)
        return httpx.Response(status, headers={"request-id": "req_12345678ABCDEF",
            "x-private-header": SECRET}, json={"type": "error",
            "error": {"type": error_type, "message": PRIVATE + SECRET},
            "private": PRIVATE})
    client = anthropic.Anthropic(api_key=SECRET, max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(reply)))
    parent = Budget(limits=Limits(usd=.1))
    ledger = Budget(limits=Limits(usd=.1), parent=parent)
    audit = tmp_path / "audit.jsonl"
    ledger.on_change = recorder(audit)
    with guard_sdk(client, ledger), pytest.raises(anthropic.APIStatusError) as caught:
        client.beta.messages.create(**deepcopy(BODY))
    assert type(caught.value).__name__ == exception_type
    rows = [json.loads(line) for line in audit.read_text().splitlines()]
    assert len(sent) == 1 and len(rows) == 2
    assert rows[0]["events"][0]["status"] == "reserved"
    event = rows[-1]["events"][0]
    assert event["status"] == "unknown_usage"
    assert event["diagnostic"] == {"exception_type": exception_type,
        "http_status": status, "request_id": "req_12345678ABCDEF",
        "provider_error_type": error_type}
    assert event["failed_ns"] >= event["reserved_ns"]
    assert not rows[-1]["cost_certified"] and not parent.certified
    assert rows[-1]["reserved_nanodollars"] > 0 and rows[-1]["usd"] is None
    serialized = audit.read_text()
    assert all(value not in serialized for value in (SECRET, PRIVATE, "PRIVATE_INPUT_FIXTURE"))
    assert not ({"message", "body", "headers", "request", "url", "traceback"} & event["diagnostic"].keys())


def test_timeout_is_persisted_without_inventing_http_response_or_usage(tmp_path):
    sent = []
    def timeout(request):
        sent.append(request)
        raise httpx.ReadTimeout(PRIVATE + SECRET, request=request)
    client = anthropic.Anthropic(api_key=SECRET, max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(timeout)))
    ledger = Budget(limits=Limits(usd=.1))
    audit = tmp_path / "audit.jsonl"
    ledger.on_change = recorder(audit)
    with guard_sdk(client, ledger), pytest.raises(anthropic.APITimeoutError):
        client.beta.messages.create(**deepcopy(BODY))
    event = json.loads(audit.read_text().splitlines()[-1])["events"][0]
    assert event["diagnostic"] == {"exception_type": "APITimeoutError",
        "http_status": None, "request_id": None, "provider_error_type": None}
    assert len(sent) == 1 and not ledger.certified and ledger.reserved_usd > 0
    assert SECRET not in audit.read_text() and PRIVATE not in audit.read_text()


def test_local_exception_type_is_recorded_without_exception_message(tmp_path):
    from types import SimpleNamespace
    def fail(*args, **kwargs):
        raise TypeError(PRIVATE + SECRET)
    client = SimpleNamespace(max_retries=0,
        beta=SimpleNamespace(messages=SimpleNamespace(_post=fail)))
    ledger = Budget(limits=Limits(usd=.1))
    audit = tmp_path / "audit.jsonl"
    ledger.on_change = recorder(audit)
    with guard_sdk(client, ledger), pytest.raises(TypeError):
        client.beta.messages._post("/v1/messages", body=deepcopy(BODY))
    event = json.loads(audit.read_text().splitlines()[-1])["events"][0]
    assert event["diagnostic"] == {"exception_type": "TypeError",
        "http_status": None, "request_id": None, "provider_error_type": None}
    assert PRIVATE not in audit.read_text() and SECRET not in audit.read_text()


@pytest.mark.parametrize("request_id,provider_type", [
    (SECRET, SECRET), ("req_" + "a" * 300, PRIVATE), ("req_bad\ncontent", {"type": PRIVATE}),
])
def test_untrusted_metadata_cannot_copy_content_or_secrets(request_id, provider_type):
    response = httpx.Response(400, request=httpx.Request("POST", "https://example.invalid"))
    error = anthropic.BadRequestError(PRIVATE, response=response, body=None)
    # The real SDK exposes these attributes; refuse values outside its metadata contract.
    error.request_id = request_id
    error.type = provider_type
    result = budget_module.sdk_error_metadata(error)
    assert result == {"exception_type": "BadRequestError", "http_status": 400,
                      "request_id": None, "provider_error_type": None}

