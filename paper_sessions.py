"""Fail-closed replay guards for simulation accounts; never repairs saved evidence."""
import csv
from datetime import date
from pathlib import Path


def canonical_session(value):
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise ValueError('noncanonical account session')
    return value


def recorded_sessions(path):
    """Ambiguous legacy ledgers require review, never silent normalization."""
    path = Path(path)
    if not path.exists():
        return []
    with path.open(newline='', encoding='utf-8') as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or 'date_utc' not in reader.fieldnames:
            raise ValueError('performance ledger missing date_utc')
        sessions = [canonical_session(row.get('date_utc')) for row in reader]
    if len(sessions) != len(set(sessions)):
        raise ValueError('duplicate performance sessions; historical reconciliation required')
    if sessions != sorted(sessions):
        raise ValueError('unordered performance sessions; historical reconciliation required')
    return sessions


def already_processed(state, session, path, *, crypto=False):
    canonical_session(session)
    sessions = recorded_sessions(path)
    # Legacy crypto last_run_date was a Chicago wall-clock label. It cannot
    # authenticate source identity. Bound new processing conservatively by it,
    # but store future source identity separately and never rewrite old rows.
    last = state.get('last_price_session') if crypto else state.get('last_run_date')
    bounds = list(sessions)
    for value in (last, state.get('last_run_date')):
        if value is not None:
            bounds.append(canonical_session(value))
    if bounds and session < max(bounds):
        raise ValueError('source session precedes saved account evidence')
    return session in bounds
