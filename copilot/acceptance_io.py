"""Private, atomic, sanitized artifacts for the future sealed 5C runner."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile


def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def seal_record_path(directory):
    directory=Path(directory)
    return directory.with_name(directory.name+'.seal-record.json')


def register_seal(directory):
    """Create an exclusive external hash record; never replace a prior record."""
    path=seal_record_path(directory)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as stream:
        json.dump({'schema':'batch5c-seal-record-v1',
                   'seal_sha256':sha256(Path(directory)/'seal.json')},stream)
        stream.write('\n');stream.flush();os.fsync(stream.fileno())


def write_json(path,value):
    path=Path(path)
    fd,temporary=tempfile.mkstemp(prefix='.'+path.name+'.',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as stream:
            json.dump(value,stream,ensure_ascii=False,allow_nan=False,indent=2);stream.write('\n')
            stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
        directory=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(directory)
        finally:os.close(directory)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)


_SECRET=re.compile(r'(?i)(?:sk-(?:ant-)?[A-Za-z0-9_-]{8,}|(?:api[_-]?key|authorization|password|secret|token)\s*[:=]\s*[^\s,;]+)')
_PATH=re.compile(r'(?<![:\w])/(?:Users|tmp|private|home|var)/[^\s\"\'<>]+')


def sanitize(value):
    if isinstance(value,dict):
        return {k:('[redacted]' if k.lower() in {'api_key','authorization','password','secret','access_token'} else sanitize(v)) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [sanitize(v) for v in value]
    if isinstance(value,str):return _PATH.sub('[local-path]',_SECRET.sub('[redacted]',value))
    if value is None or type(value) in (int,float,bool):return value
    raise ValueError('Unsupported trace value')
