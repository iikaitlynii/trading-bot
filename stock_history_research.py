"""Publish stock HLCV only after complete immutable-universe validation."""
from pathlib import Path
from data_contracts.ingestion import atomic, collect, verified_export

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'research' / 'stock_history.csv'
SYMBOLS = ('AAPL', 'MSFT', 'NVDA', 'AMZN')


def main():
    manifest = collect('stock', ROOT)
    # Compatibility export; immutable manifest/export remains the authority.
    atomic(OUT, verified_export(ROOT / manifest['export']))


if __name__ == '__main__':
    main()
