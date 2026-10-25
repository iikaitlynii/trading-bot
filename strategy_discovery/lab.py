"""Small allowlisted transcript parser; transcript text is always inert data."""
import hashlib
import json
import math
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path

FIELDS = {
    'timeframe': r'Timeframe: (daily)\.',
    'indicators': r'Indicators: SMA\((\d+)\), SMA\((\d+)\), SMA\((\d+)\)\.',
    'entry': r'Entry: close above regime SMA and fast SMA above slow SMA\.',
    'exit': r'Exit: fast SMA below slow SMA or close below regime SMA\.',
    'risk': r'Risk: stop (\d+(?:\.\d+)?) percent below entry fill; max weight (\d+(?:\.\d+)?) percent\.',
    'execution': r'Execution: long only, same close, no leverage, same-session reentry permitted\.',
}


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def discover(metadata, query):
    """Search a saved public metadata snapshot; no network or caption scraping."""
    tokens = query.casefold().split()
    return [deepcopy(v) for v in metadata if all(t in (v['title'] + ' ' + v.get('description', '')).casefold() for t in tokens)]


def extract(source):
    if source.get('permission', {}).get('basis') not in {'author-created fixture', 'creator permission', 'owned captions'}:
        raise ValueError('documented transcript permission required')
    if not source['permission'].get('reference'):
        raise ValueError('permission reference required')
    if not re.fullmatch(r'https://www\.youtube\.com/watch\?v=[A-Za-z0-9_-]{11}', source.get('video_url', '')):
        raise ValueError('canonical video URL required')
    datetime.fromisoformat(source['retrieved_at'].replace('Z', '+00:00'))
    evidence = {field: [] for field in FIELDS}
    unmatched = []
    previous = -1
    for segment in source['segments']:
        start, end, text = segment['start'], segment['end'], segment['text']
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (start, end)) or start < 0 or start < previous or end <= start:
            raise ValueError('invalid or unordered transcript timestamps')
        previous = end
        matched = False
        for field, pattern in FIELDS.items():
            match = re.fullmatch(pattern, text)
            if match:
                evidence[field].append({'quote': text, 'start': start, 'end': end,
                                        'url': source['video_url'] + '&t=' + str(int(start)),
                                        'values': list(match.groups())})
                matched = True
        if not matched:
            unmatched.append({'start': start, 'end': end, 'quote': text})
    issues = [f'{k}: expected exactly one explicit supported rule' for k, v in evidence.items() if len(v) != 1]
    if unmatched:
        issues.append('unparsed transcript content requires human interpretation')
    cfg = None
    if not issues:
        fast, slow, regime = map(int, evidence['indicators'][0]['values'])
        stop, weight = map(float, evidence['risk'][0]['values'])
        cfg = dict(fast=fast, slow=slow, regime=regime, stop=stop/100, max_weight=weight/100)
        try:
            validate_config(cfg)
        except ValueError as exc:
            issues.append(str(exc))
    return dict(source=deepcopy(source), source_sha256=digest(source), evidence=evidence,
                unmatched=unmatched, uncertainties=issues, config=cfg,
                status='needs_human_review', parser='controlled-transcript-v1')


def validate_config(cfg):
    if not isinstance(cfg, dict) or set(cfg) != {'fast', 'slow', 'regime', 'stop', 'max_weight'}:
        raise ValueError('unsupported configuration fields')
    if any(type(cfg[k]) is not int for k in ('fast', 'slow', 'regime')):
        raise ValueError('integer SMA periods required')
    if not 2 <= cfg['fast'] < cfg['slow'] <= cfg['regime'] <= 250:
        raise ValueError('unsupported SMA period ordering or bounds')
    for key, limit in [('stop', .20), ('max_weight', .20)]:
        v = cfg[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 < v <= limit:
            raise ValueError('unsupported risk bounds: ' + key)


def approve(candidate, review):
    """A review is a local auditable attestation, not an authenticated identity."""
    # Reparse original evidence so edits cannot remove uncertainty or swap rules.
    fresh = extract(candidate['source'])
    if candidate != fresh or fresh['uncertainties']:
        raise ValueError('candidate modified, ambiguous or incomplete')
    if review.get('decision') != 'approve' or review.get('candidate_sha256') != digest(candidate):
        raise ValueError('explicit review bound to candidate hash required')
    if not all(isinstance(review.get(k), str) and review[k].strip() for k in ('reviewer', 'reviewed_at', 'rationale')):
        raise ValueError('review identity, timestamp and rationale required')
    datetime.fromisoformat(review['reviewed_at'].replace('Z', '+00:00'))
    return dict(schema=1, simulation_only=True, template='sma_regime_v1',
                candidate=deepcopy(candidate), review=deepcopy(review))


def configuration(spec):
    if set(spec) != {'schema', 'simulation_only', 'template', 'candidate', 'review'} or spec['schema'] != 1 or spec['simulation_only'] is not True or spec['template'] != 'sma_regime_v1':
        raise ValueError('unsupported simulation specification')
    if approve(spec['candidate'], spec['review']) != spec:
        raise ValueError('invalid specification')
    return deepcopy(spec['candidate']['config'])


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))
