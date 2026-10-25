"""Generate fixed artificial observations and a predeclared demonstration protocol."""
from pathlib import Path
import numpy as np
import pandas as pd
from research.validation.evaluate import UNIVERSE, RULE_SHA256, ROOT, digest, encoded


def create(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    dates = pd.bdate_range('2020-01-01', periods=660)
    x = np.arange(len(dates))
    prices = pd.DataFrame({asset: 100 * np.exp(.0003*x + .12*np.sin(x/(12+i)) + .04*np.cos(x/7)) for i, asset in enumerate(UNIVERSE)}, index=dates)
    prices.index.name = 'date'
    raw = prices.to_csv(float_format='%.10f', lineterminator='\n').encode()
    (destination/'synthetic.csv').write_bytes(raw)
    cfg = dict(evidence='synthetic', source='deterministic analytic fixture; not market prices',
               retrieved_at='not applicable: generated', session_convention='artificial weekdays for ALL assets, not exchange or UTC crypto calendar',
               adjustment_basis='none: artificial prices', dataset='synthetic.csv', dataset_sha256=digest(raw),
               universe=UNIVERSE, rule_sha256=RULE_SHA256, fee_bps=10, slippage_bps=10,
               evaluator_sha256=digest((ROOT/'research/validation/evaluate.py').read_bytes()),
               periods={name:[str(dates[a].date()),str(dates[b].date())] for name,a,b in [('train',230,359),('selection',360,479),('evaluation',480,659)]},
               expected_sessions=dates.strftime('%Y-%m-%d').tolist())
    (destination/'protocol.json').write_bytes(encoded(cfg))


if __name__ == '__main__':
    create(Path(__file__).parent/'fixture')
