"""Evidence-backed, dashboard-only weekly archives. No network or messaging."""
import argparse
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re

from .evaluate import evaluate, research_rank, synthetic_prices
from .lab import configuration, digest, encoded, extract, load

SCOPE = 'SYNTHETIC FIXTURES ONLY — no actual video discoveries or historical evidence'


def timestamp(value):
    if not isinstance(value, str) or not value.endswith('Z'):
        raise ValueError('explicit UTC timestamp ending in Z required')
    return datetime.fromisoformat(value[:-1] + '+00:00')


def week(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('ISO Monday date required')
    start = date.fromisoformat(value)
    if start.weekday() != 0:
        raise ValueError('week must start on Monday (UTC)')
    return start, start + timedelta(days=7)


def build_report(ledger, week_start, generated_at):
    """Only explicit dated review records count; fixtures are never discoveries.

    Callers attest review activity, not provider authenticity. Real-source and
    historical publication remain blocked until an authenticated adapter exists.
    """
    start, end = week(week_start)
    generated = timestamp(generated_at)
    if generated > datetime.now(timezone.utc):
        raise ValueError('generation timestamp cannot be in the future')
    if generated.date() < end:
        raise ValueError('archive only completed UTC weeks; do not invent future activity')
    if set(ledger) != {'schema_version', 'reviews'} or ledger['schema_version'] != 1 or not isinstance(ledger['reviews'], list):
        raise ValueError('unsupported evidence ledger')
    sources, candidates, seen = [], [], set()
    for record in ledger['reviews']:
        if not isinstance(record, dict) or set(record) - {'reviewed_at', 'reviewer', 'source', 'specification'}:
            raise ValueError('unsupported activity or claimed results')
        reviewed = timestamp(record['reviewed_at'])
        if reviewed > generated:
            raise ValueError('future review activity')
        if not isinstance(record['reviewer'], str) or not record['reviewer'].strip():
            raise ValueError('reviewer required')
        source = record['source']
        # A public URL, permission assertion or renamed CSV is not authenticity.
        if source.get('synthetic') is not True or source.get('permission', {}).get('basis') != 'author-created fixture':
            raise ValueError('real-source publication unsupported; retain EMPTY / UNVALIDATED')
        candidate = extract(source)
        if timestamp(source['retrieved_at']) > reviewed:
            raise ValueError('review predates source acquisition')
        if not start <= reviewed.date() < end:
            continue
        key = digest(source)
        if key in seen:
            raise ValueError('duplicate source review would inflate weekly activity')
        seen.add(key)
        result = None
        if record.get('specification') is not None:
            spec = record['specification']
            configuration(spec)
            if spec['candidate'] != candidate or timestamp(spec['review']['reviewed_at']) > reviewed:
                raise ValueError('specification must match reviewed evidence and chronology')
            # Never accept caller-supplied performance metrics.
            result = evaluate(spec, synthetic_prices())
        sources.append(dict(source_sha256=key, reviewed_at=record['reviewed_at'], reviewer=record['reviewer'], source=source))
        candidates.append(dict(candidate_sha256=digest(candidate), candidate=candidate,
                               quality=research_rank(candidate, result), simulation_state='UNVALIDATED' if result else 'NOT RUN', result=result))
    sources.sort(key=lambda r: r['source_sha256'])
    candidates.sort(key=lambda r: (-r['quality']['score'], r['candidate_sha256']))
    return dict(schema_version=1, simulation_only=True, scope=SCOPE, week_start=start.isoformat(),
                week_end=(end-timedelta(days=1)).isoformat(), generated_at_utc=generated_at,
                activity_state='RECORDED FIXTURE REVIEWS' if sources else 'EMPTY',
                simulation_state='UNVALIDATED' if any(c['result'] for c in candidates) else 'NOT RUN',
                historical_state='UNVALIDATED', sources=sources, candidates=candidates,
                counts=dict(sources_reviewed=len(sources), candidates=len(candidates),
                            ambiguous=sum(bool(c['candidate']['uncertainties']) for c in candidates),
                            simulations=sum(c['result'] is not None for c in candidates)),
                ledger_sha256=digest(ledger), evidence_ledger=ledger,
                limitations=['Recorded activity is supplied by a reviewer, not authenticated by this offline tool.',
                             'Only original synthetic fixture reviews are supported; no actual source discoveries.',
                             'No historical results, independent OOS evidence or profitability claims.',
                             'EMPTY means a report ran with no recorded reviews; NOT RUN means no simulation or no report.'])


def validate_report(report):
    expected = build_report(report['evidence_ledger'], report['week_start'], report['generated_at_utc'])
    if expected != report:
        raise ValueError('weekly report does not match its dated evidence and recomputed simulations')
    return report


def archive_index(directory):
    directory = Path(directory)
    path = directory/'index.json'
    if path.is_symlink():
        raise ValueError('archive index symlinks unsupported')
    index = load(path) if path.exists() else dict(schema_version=1, reports=[])
    if set(index) != {'schema_version', 'reports'} or index['schema_version'] != 1 or not isinstance(index['reports'], list):
        raise ValueError('unsupported archive index')
    seen = set()
    for entry in index['reports']:
        if set(entry) != {'week_start', 'path', 'sha256'}:
            raise ValueError('unsupported archive entry')
        week(entry['week_start'])
        if entry['week_start'] in seen or entry['path'] != entry['week_start']+'.json' or not re.fullmatch(r'[a-f0-9]{64}', entry['sha256']):
            raise ValueError('duplicate or unsafe archive entry')
        seen.add(entry['week_start'])
        report_path = directory/entry['path']
        if report_path.is_symlink():
            raise ValueError('archive symlinks unsupported')
        raw = report_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry['sha256']:
            raise ValueError('archive report hash mismatch')
        saved = json.loads(raw)
        if saved['week_start'] != entry['week_start'] or saved['schema_version'] != 1 or saved['simulation_only'] is not True or saved['scope'] != SCOPE or saved['historical_state'] != 'UNVALIDATED':
            raise ValueError('archive classification mismatch')
    if index['reports'] != sorted(index['reports'], key=lambda e: e['week_start'], reverse=True):
        raise ValueError('archive order must be newest first')
    return index


@contextmanager
def archive_lock(directory):
    lock = directory/'.weekly.lock'
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        yield
    finally:
        os.close(fd)
        lock.unlink()


def publish(report, directory):
    """Immutable per-week files; idempotent reruns, no overwrite or backfill."""
    validate_report(report)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with archive_lock(directory):
        index = archive_index(directory)
        raw = encoded(report)
        entry = dict(week_start=report['week_start'], path=report['week_start']+'.json', sha256=hashlib.sha256(raw).hexdigest())
        existing = next((e for e in index['reports'] if e['week_start'] == entry['week_start']), None)
        if existing:
            if existing != entry:
                raise ValueError('archived week is immutable; refusing replacement')
            return index
        target = directory/entry['path']
        # Never replace an orphan file or symlink, even if not in the index.
        with target.open('xb') as f:
            f.write(raw)
        index['reports'].append(entry)
        index['reports'].sort(key=lambda e: e['week_start'], reverse=True)
        temporary = directory/'.index.tmp'
        temporary_created = False
        try:
            with temporary.open('xb') as f:
                temporary_created = True
                f.write(encoded(index))
            temporary.replace(directory/'index.json')
        except BaseException:
            target.unlink()
            raise
        finally:
            if temporary_created and temporary.exists() and not temporary.is_symlink():
                temporary.unlink()
        return index


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ledger', type=Path, required=True)
    p.add_argument('--week-start', required=True)
    p.add_argument('--archive', type=Path, default=Path('docs/strategy-discovery'))
    a = p.parse_args()
    now = datetime.now(timezone.utc)
    generated_at = now.isoformat(timespec='seconds').replace('+00:00', 'Z')
    publish(build_report(load(a.ledger), a.week_start, generated_at), a.archive)
    print('Saved dashboard-only weekly archive. No external messages sent.')


if __name__ == '__main__':
    main()
