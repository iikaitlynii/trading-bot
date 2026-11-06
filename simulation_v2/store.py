"""Immutable multi-file generations with a single fsynced publication pointer.

Readers never combine files from different transactions. A complete unpublished
generation blocks advancement until explicit, hash-checked roll-forward recovery.
Incomplete staging directories are unreferenced and never used as account data.
"""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile

from .model import MODEL, canonical, digest, reconcile

FILES = ('state.json', 'orders.json', 'fills.json', 'valuations.json')


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write(path, payload):
    with path.open('xb') as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def atomic(path, payload):
    fd, tmp = tempfile.mkstemp(prefix='.pointer-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        sync_dir(path.parent)
    finally:
        Path(tmp).unlink(missing_ok=True)


def validate_extension(base, account):
    if base is not None:
        for name in ('orders', 'fills', 'valuations'):
            # Order status may transition; all other saved order facts are immutable.
            old, new = base[name], account[name]
            if len(new) < len(old):
                raise ValueError('history truncation')
            for a,b in zip(old,new):
                if name == 'orders':
                    if {k:v for k,v in a.items() if k != 'status'} != {k:v for k,v in b.items() if k != 'status'} or (a['status'] != 'PENDING' and a != b):
                        raise ValueError('order history rewritten')
                elif a != b:
                    raise ValueError('history rewritten')
        for name in ('created_at', 'initial_cash', 'market', 'symbols', 'assumptions', 'model', 'code_sha256'):
            if base.get(name) != account.get(name):
                raise ValueError('account configuration rewritten')


class Store:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def locked(self):
        self.path.mkdir(parents=True, exist_ok=True)
        with (self.path / '.lock').open('a') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield self
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    def pointer(self):
        p = self.path / 'current.json'
        if not p.exists():
            return None
        value = json.loads(p.read_bytes())
        if set(value) != {'generation'} or len(value['generation']) != 64 or any(c not in '0123456789abcdef' for c in value['generation']):
            raise ValueError('invalid transaction pointer')
        return value['generation']

    def generation(self, key):
        if not isinstance(key,str) or len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
            raise ValueError('invalid generation key')
        folder = self.path / 'generations' / key
        payload = (folder / 'manifest.json').read_bytes()
        manifest = json.loads(payload)
        if hashlib.sha256(payload).hexdigest() != key or manifest['schema_version'] != 2 or set(manifest['files']) != set(FILES):
            raise ValueError('invalid transaction manifest')
        parts = {}
        for name, expected in manifest['files'].items():
            raw = (folder / name).read_bytes()
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError('transaction file hash mismatch')
            parts[name] = json.loads(raw)
        account = parts['state.json']
        for name in FILES[1:]:
            account[name[:-5]] = parts[name]
        reconcile(account)
        if (manifest['simulation_only'] is not True or manifest['session'] != account['last_session']
                or manifest['model'] != MODEL or manifest['account_sha256'] != digest(account)):
            raise ValueError('manifest account mismatch')
        return account, manifest

    def load(self):
        key = self.pointer()
        if key is None:
            return None
        seen = set()
        current, manifest = self.generation(key)
        # Check all committed ancestry, not just the newest checkpoint.
        while key:
            if key in seen:
                raise ValueError('transaction ancestry cycle')
            seen.add(key)
            child, manifest = self.generation(key)
            key = manifest['parent']
            if key:
                parent, _ = self.generation(key)
                validate_extension(parent, child)
        return current

    def prepared(self):
        current = self.pointer()
        directory = self.path / 'generations'
        return [p.name for p in directory.iterdir() if p.is_dir() and
                self.generation(p.name)[1]['parent'] == current and p.name != current] if directory.exists() else []

    def commit(self, account, expected_parent, *, interrupt=None):
        reconcile(account)
        if self.pointer() != expected_parent:
            raise ValueError('concurrent account update')
        if self.prepared():
            raise ValueError('unpublished transaction requires recovery')
        base = self.load()
        if base is not None and account == base:
            return expected_parent
        validate_extension(base, account)
        self.path.mkdir(parents=True, exist_ok=True)
        directory = self.path / 'generations';directory.mkdir(exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix='.staging-', dir=self.path))
        parts = {name: account[name[:-5]] for name in FILES[1:]}
        parts['state.json'] = {k:v for k,v in account.items() if k not in ('orders', 'fills', 'valuations')}
        hashes = {}
        for name in FILES:
            payload = canonical(parts[name]);write(stage / name, payload)
            hashes[name] = hashlib.sha256(payload).hexdigest()
            if interrupt:
                interrupt(name)
        manifest = dict(schema_version=2, simulation_only=True, parent=expected_parent,
                        session=account['last_session'], model=MODEL, account_sha256=digest(account), files=hashes)
        payload = canonical(manifest);key = hashlib.sha256(payload).hexdigest()
        write(stage / 'manifest.json', payload);sync_dir(stage)
        os.replace(stage, directory / key);sync_dir(directory)
        if interrupt:
            interrupt('prepared')
        atomic(self.path / 'current.json', canonical(dict(generation=key)))
        if interrupt:
            interrupt('published')
        return key

    def recover(self, key):
        # Caller must hold locked(); no guessing among conflicting transactions.
        if key not in self.prepared() or self.prepared() != [key]:
            raise ValueError('recovery requires one exact prepared generation')
        account, manifest = self.generation(key)
        if manifest['parent'] != self.pointer():
            raise ValueError('recovery parent changed')
        # Prepared generation was built before publication. Validate its ancestry.
        validate_extension(self.load(), account)
        atomic(self.path / 'current.json', canonical(dict(generation=key)))
        return account
