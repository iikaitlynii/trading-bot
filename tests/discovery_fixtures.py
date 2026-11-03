"""Generate test-only weekly fixtures under work/, never the public archive."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from strategy_discovery.weekly import build_report
from strategy_discovery.lab import load, encoded


def fixtures():
    sources=load('strategy_discovery/samples/transcripts.json')
    reviews=[dict(reviewed_at='2026-10-25T02:00:00Z',reviewer='fixture reviewer',source=s) for s in sources]
    reviews[0]['specification']=load('strategy_discovery/specifications/demo.json')
    full=build_report(dict(schema_version=1,reviews=reviews),'2026-10-19','2026-10-26T03:00:00Z')
    empty=build_report(dict(schema_version=1,reviews=[]),'2026-10-12','2026-10-26T03:00:00Z')
    return dict(full=full,empty=empty)


if __name__=='__main__':
    path=Path('work/discovery-fixtures.json');path.parent.mkdir(exist_ok=True);path.write_bytes(encoded(fixtures()))
