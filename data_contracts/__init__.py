"""Immutable, fail-closed daily research snapshots; no trading or network calls."""
from dataclasses import asdict, dataclass
from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import quote

from .sessions import VERSION, aware, latest_completed, session_close, sessions

SCHEMA = 1


@dataclass(frozen=True)
class Bar:
    session: str
    close: float


@dataclass(frozen=True)
class Provenance:
    symbol: str
    market: str
    source_url: str
    retrieved_at: str
    as_of: str
    start: str
    end: str
    adjustment: str
    dependencies: tuple[tuple[str, str], ...]
    code_version: str
    classification: str = 'historical research'


@dataclass(frozen=True)
class Snapshot:
    provenance: Provenance
    bars: tuple[Bar, ...]
    timezone: str
    session_convention: str
    calendar_version: str
    schema_version: int = SCHEMA


class ContractError(ValueError):
    def __init__(self, issues):
        self.issues = tuple(issues)
        super().__init__('; '.join(self.issues))


def endpoint(symbol):
    if not isinstance(symbol, str) or not symbol or symbol.strip() != symbol:
        raise ValueError('nonempty symbol required')
    return 'https://query1.finance.yahoo.com/v8/finance/chart/' + quote(symbol, safe='')


def instant(value):
    return aware(datetime.fromisoformat(value))


def validate(snapshot):
    """Return explicit issue codes; invalid data never becomes a sell signal."""
    errors = []
    p = snapshot.provenance
    try:
        if snapshot.schema_version != SCHEMA:
            raise ValueError('unsupported schema')
        stock = p.market == 'stock'
        if p.market not in ('stock', 'crypto'):
            raise ValueError('unsupported market')
        if (snapshot.timezone, snapshot.session_convention, snapshot.calendar_version) != (
                'America/New_York' if stock else 'UTC',
                'XNYS regular session' if stock else 'UTC day [00:00, next 00:00)',
                VERSION if stock else 'utc-daily-v1'):
            raise ValueError('session metadata mismatch')
        if p.source_url != endpoint(p.symbol):
            raise ValueError('source endpoint/symbol mismatch')
        if p.adjustment not in ('raw_close', 'adjusted_close'):
            raise ValueError('explicit adjustment basis required')
        if not isinstance(p.dependencies, tuple) or not p.dependencies or any(
                not isinstance(pair, tuple) or len(pair) != 2 or
                any(not isinstance(v, str) or not v for v in pair) for pair in p.dependencies):
            raise ValueError('dependency versions required')
        if len(dict(p.dependencies)) != len(p.dependencies) or not isinstance(p.code_version, str) or not p.code_version:
            raise ValueError('unique dependency versions and code version required')
        if p.classification not in ('historical research', 'synthetic illustrative fixture'):
            raise ValueError('invalid evidence classification')
        as_of, retrieved = instant(p.as_of), instant(p.retrieved_at)
        if retrieved < as_of:
            raise ValueError('retrieval predates as-of')
        start, end = date.fromisoformat(p.start), date.fromisoformat(p.end)
        if (start.isoformat(), end.isoformat()) != (p.start, p.end):
            raise ValueError('canonical ISO session dates required')
        expected = sessions(start, end, p.market)
        latest = latest_completed(as_of, p.market)
        if end != latest:
            errors.append('STALE' if end < latest else 'UNFINISHED')
        if not expected:
            errors.append('MISSING')
        if not isinstance(snapshot.bars, tuple) or any(not isinstance(b, Bar) for b in snapshot.bars):
            raise ValueError('immutable bars required')
        labels = []
        for bar in snapshot.bars:
            day = date.fromisoformat(bar.session)
            if day.isoformat() != bar.session:
                raise ValueError('canonical ISO session date required')
            labels.append(day)
            close = session_close(day, p.market)
            if close is None or day < start or day > end:
                errors.append('INVALID_SESSION')
            elif close > as_of:
                errors.append('UNFINISHED')
            if isinstance(bar.close, bool) or not isinstance(bar.close, (int, float)) or not math.isfinite(bar.close) or bar.close <= 0:
                errors.append('INVALID_PRICE')
        if len(set(labels)) != len(labels):
            errors.append('DUPLICATE')
        if labels != sorted(labels):
            errors.append('UNSORTED')
        if set(expected) - set(labels):
            errors.append('MISSING')
        if not labels or max(labels) < latest:
            errors.append('STALE')
    except (ValueError, TypeError, AttributeError, OverflowError) as exc:
        errors.append('INVALID: ' + str(exc))
    return tuple(dict.fromkeys(errors))


def build(provenance, bars):
    """Require explicit session labels; never truncate, fill, sort or deduplicate."""
    stock = provenance.market == 'stock'
    snapshot = Snapshot(provenance, tuple(bars), 'America/New_York' if stock else 'UTC',
                        'XNYS regular session' if stock else 'UTC day [00:00, next 00:00)',
                        VERSION if stock else 'utc-daily-v1')
    issues = validate(snapshot)
    if issues:
        raise ContractError(issues)
    return snapshot


def canonical(snapshot):
    issues = validate(snapshot)
    if issues:
        raise ContractError(issues)
    return (json.dumps(asdict(snapshot), sort_keys=True, separators=(',', ':'),
                       allow_nan=False) + '\n').encode('utf-8')


def digest(snapshot):
    return hashlib.sha256(canonical(snapshot)).hexdigest()


def save(snapshot, directory):
    """Content-addressed create-only archive. A different payload gets a new path."""
    payload = canonical(snapshot)
    path = Path(directory) / (hashlib.sha256(payload).hexdigest() + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('xb') as stream:
            stream.write(payload)
    except FileExistsError:
        if path.read_bytes() != payload:
            raise ContractError(('HASH_MISMATCH',))
    return path


def load(path):
    path = Path(path)
    payload = path.read_bytes()
    if path.name != hashlib.sha256(payload).hexdigest() + '.json':
        raise ContractError(('HASH_MISMATCH',))
    data = json.loads(payload)
    p = data.pop('provenance')
    p['dependencies'] = tuple(tuple(pair) for pair in p['dependencies'])
    data['bars'] = tuple(Bar(**bar) for bar in data['bars'])
    snapshot = Snapshot(provenance=Provenance(**p), **data)
    if canonical(snapshot) != payload:
        raise ContractError(('NONCANONICAL',))
    return snapshot


def validate_comparison(snapshots):
    """Require same clock, window, basis and evidence class across all assets/BTC."""
    snapshots = tuple(snapshots)
    if not snapshots:
        raise ContractError(('MISSING',))
    for snapshot in snapshots:
        issues = validate(snapshot)
        if issues:
            raise ContractError(issues)
    keys = {(instant(s.provenance.as_of), s.provenance.start, s.provenance.end,
             s.provenance.adjustment, s.provenance.classification) for s in snapshots}
    if len(keys) != 1:
        raise ContractError(('MISMATCHED_COMPARISON',))
    if len({s.provenance.symbol for s in snapshots}) != len(snapshots):
        raise ContractError(('DUPLICATE_SYMBOL',))
    return snapshots
