"""End-to-end evals: agent (Claude API + tools) vs the model alone (plan 11).

Per case, two systems answer the same question ("what is z?"):
- model-only baseline: tools.official_z(predict_redshift_impl(...)) — the
  exact deterministic call behind the agent's first tool use;
- the agent: copilot.agent.run_structured(...), the full verification loop
  ending in a structured submit_report (no prose parsing).

Metrics use dz_n = |z - z_true| / (1 + z_true); 0.15 is the catastrophic
outlier threshold, 0.05 the quality threshold. The model-only columns cover
every case (they need no API), so agent errors never bias the baseline.

The results CSV is rewritten after every case: a run killed mid-way (API
credit, network) loses nothing — re-run with --resume to keep completed
cases and retry the rest. Each failing case is retried once before being
marked "error".

    python eval/run_evals.py --limit 20                    # validate harness
    python eval/run_evals.py                               # full run
    python eval/run_evals.py --resume                      # continue a run
    python eval/run_evals.py --baseline-only               # no API needed
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from copilot import agent, tools

EVAL_DIR = Path(__file__).resolve().parent
FIELDS = ["case", "z_true", "z_model", "z_final", "confidence",
          "dzn", "ok15", "ok05", "tokens", "status"]


def dz_norm(z: float, z_true: float) -> float:
    return abs(z - z_true) / (1.0 + z_true)


def write_csv(path: str, rows: list[dict]) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, restval="")
        w.writeheader()
        w.writerows(rows)


def summarize(rows: list[dict], model: str = "", usage_total: dict | None = None) -> dict:
    """Aggregate metrics; robust to rows re-read from CSV (string values)."""
    ok = [r for r in rows if r["status"] == "ok"]
    model_dzn = [
        dz_norm(float(r["z_model"]), float(r["z_true"]))
        for r in rows if r.get("z_model") not in (None, "")
    ]
    out: dict = {
        "n": len(rows),
        "n_ok": len(ok),
        "n_error": sum(r["status"] == "error" for r in rows),
        "model_only": {
            "n": len(model_dzn),
            "rate_015": round(sum(d < 0.15 for d in model_dzn) / max(len(model_dzn), 1), 3),
            "rate_005": round(sum(d < 0.05 for d in model_dzn) / max(len(model_dzn), 1), 3),
            "mae_norm": round(sum(model_dzn) / max(len(model_dzn), 1), 4),
        },
    }
    if ok:
        dzns = [float(r["dzn"]) for r in ok]
        by_conf = {
            level: {
                "n": len(sub),
                "rate_015": round(sum(int(r["ok15"]) for r in sub) / len(sub), 3),
            }
            for level in ("high", "medium", "low")
            if (sub := [r for r in ok if r["confidence"] == level])
        }
        out["agent"] = {
            "rate_015": round(sum(int(r["ok15"]) for r in ok) / len(ok), 3),
            "rate_005": round(sum(int(r["ok05"]) for r in ok) / len(ok), 3),
            "mae_norm": round(sum(dzns) / len(ok), 4),
            "by_confidence": by_conf,
            "total_tokens": sum(int(r["tokens"]) for r in ok),
        }
        if usage_total:
            cost = agent.estimate_cost_usd(model, usage_total)
            if cost is not None:
                out["agent"]["est_cost_usd_this_run"] = round(cost, 2)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="claude-haiku-4-5")
    ap.add_argument("--limit", type=int, default=0, help="0 = all cases")
    ap.add_argument("--cases", default=str(EVAL_DIR / "cases"))
    ap.add_argument("--out", default=str(EVAL_DIR / "results.csv"))
    ap.add_argument("--resume", action="store_true",
                    help="keep status=ok rows already in --out, retry the rest")
    ap.add_argument("--baseline-only", action="store_true",
                    help="no API calls: model-only prediction per case")
    a = ap.parse_args()

    with open(Path(a.cases) / "labels.csv") as f:
        labels = {r["case"]: float(r["z_true"]) for r in csv.DictReader(f)}
    items = sorted(labels)[: a.limit or None]

    done: dict[str, dict] = {}
    if a.resume and Path(a.out).exists():
        with open(a.out) as f:
            done = {r["case"]: r for r in csv.DictReader(f) if r["status"] == "ok"}

    rows, usage_total = [], {}
    for i, case in enumerate(items):
        if case in done:
            rows.append(done[case])
            continue
        z_true = labels[case]
        npz = str(Path(a.cases) / f"{case}.npz")
        z_model = tools.official_z(tools.predict_redshift_impl(npz))
        row = {"case": case, "z_true": z_true, "z_model": round(z_model, 4),
               "status": "baseline"}
        if not a.baseline_only:
            r = None
            for attempt in (1, 2):
                try:
                    r = agent.run_structured(npz, model=a.model)
                except Exception as e:
                    print(f"[{case}] attempt {attempt} ERROR {e!r}")
                if r is not None:
                    break
            if r is None:
                row["status"] = "error"
            else:
                dzn = dz_norm(r["z_final"], z_true)
                for k, v in r["usage"].items():
                    usage_total[k] = usage_total.get(k, 0) + v
                row.update(
                    z_final=r["z_final"], confidence=r["confidence"],
                    dzn=round(dzn, 4), ok15=int(dzn < 0.15),
                    ok05=int(dzn < 0.05),
                    tokens=r["tokens_in"] + r["tokens_out"], status="ok",
                )
        rows.append(row)
        write_csv(a.out, rows)  # after every case: a killed run loses nothing
        z_final = row.get("z_final")
        tail = (f"z_final={z_final:.3f}  ok15={bool(row.get('ok15'))}"
                if z_final is not None else row["status"])
        print(f"[{i + 1}/{len(items)}] {case}  z_true={z_true:.3f}  "
              f"z_model={z_model:.3f}  {tail}")

    print(json.dumps(summarize(rows, a.model, usage_total), indent=2))


if __name__ == "__main__":
    main()
