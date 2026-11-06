"""Read-only dashboard export. Saved v2 valuations never grant account health."""
from datetime import datetime, timezone
from pathlib import Path
from .model import MODEL, ASSUMPTION, valuation
from .runner import legacy_guard
from .store import Store, atomic

ACCOUNTS = [('stock','stock'),('crypto','crypto')] + [('forward-'+name,'stock') for name in (
    'current_20_50','faster_10_30','conservative_30_75','low_concentration_20_50')]


def build(root=Path('.'), now=None):
    root=Path(root);now=now or datetime.now(timezone.utc)
    rows=[]
    for name,market in ACCOUNTS:
        row=dict(id=name,model=MODEL,availability='UNAVAILABLE',reason='No v2 account evidence. Legacy results use earlier same-close/zero-cost assumptions.',
                 pending_orders=None,accounting=None,positions=None,fills=None,last_session=None)
        try:
            legacy_guard(root,market,name)
            store=Store(root/'simulation-v2'/name)
            generation=store.pointer()
            account=store.load()
            if store.pointer() != generation:
                raise ValueError("Concurrent publication; retry export")
            if store.prepared():
                raise ValueError('Unpublished transaction requires validated recovery')
            if account is not None:
                row.update(availability='SAVED_SIMULATION',reason='Saved forward-only simulation evidence; consult independent health above. Valuation may be stale.',
                           generation=generation,last_session=account['last_session'],assumptions=account['assumptions'],
                           pending_orders=[o for o in account['orders'] if o['status']=='PENDING'],positions=account['positions'],fills=account['fills'],
                           accounting=valuation(account,account['valuations'][-1]['marks']) if account['valuations'] else None,
                           risk=account['valuations'][-1]['risk'] if account['valuations'] else None)
        except (OSError,ValueError,KeyError,TypeError) as exc:
            row.update(availability='BLOCKED',reason=str(exc))
        rows.append(row)
    return dict(schema_version=2,model=MODEL,simulation_only=True,checked_at=now.isoformat(),assumption_label=ASSUMPTION,accounts=rows)


def main():
    from .model import canonical
    path=Path('docs/simulation-v2/status.json');path.parent.mkdir(parents=True,exist_ok=True)
    atomic(path,canonical(build()))


if __name__=='__main__':main()
