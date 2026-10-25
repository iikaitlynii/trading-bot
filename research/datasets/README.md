# Daily research dataset contract v1

Parent: phase #1, **“Check missing, stale, duplicate records”** and **“Maintain strategy version and comparison history”**; phase #4 benchmark prerequisites. Implements the scope in `research/next_round/02-data-provenance.md`. This is an additive research boundary: consumers must explicitly adopt it in future integration work. Saved paper records, paper engines, strategy rules, and `market_data.py` are preserved.

## Consumer API and eligibility

`data_contracts.build(Provenance(...), bars)` accepts daily `Bar(session="YYYY-MM-DD", close=...)` records. It raises `ContractError` carrying issue codes if the input is unusable. `validate(snapshot)` returns those codes without producing a trading signal. Consumers must suppress research/comparisons when validation fails; never turn failure into a defensive/sell signal, fill prices, remove unfinished rows silently, sort away ordering errors or deduplicate ambiguous data.

Supply an explicit inclusive start/end window and timezone-aware as-of instant. End must equal the latest completed session at that instant; start is required even if its first session is absent from the feed. Every expected session must be present, in ascending order, exactly once, with a finite positive close. Stock weekends/holidays are invalid rows, rather than expected missing records. An empty feed is missing and stale; an omitted last session is both missing and stale. Interior omissions are missing even when the endpoint is current. A newly retrieved old series is still stale. A row whose close time is after as-of is unfinished. Invalid metadata, dates or unsupported calendars fail closed.

`validate_comparison([asset, ..., btc_benchmark])` validates each snapshot and requires a common as-of instant, window, adjustment basis and evidence classification; equivalent timezone offsets represent the same instant. Symbols must be unique. Stock and crypto may have different interior session grids, which consumers must explicitly align without filling or inventing returns. This API does not calculate returns or alter strategies.

## Session calendar

Stocks use **XNYS regular sessions only**, with labels in `America/New_York`. The versioned offline calendar in `data_contracts/sessions.py` covers **2024–2027** inclusive. It includes NYSE holidays, the January 9, 2025 Carter mourning closure, and published 13:00 early closes; normal close is 16:00. `zoneinfo` converts these boundaries to UTC across daylight saving changes. The calendar rejects dates beyond its reviewed coverage, including a latest-session search that would cross the lower boundary. Extend and review it before using older history or later years. This is not a universal calendar for every stock exchange or unscheduled future closures.

Calendar reference endpoints (reference links, not fetched by tests):
- https://www.nyse.com/markets/hours-calendars
- https://ir.theice.com/press/news-details/2024/NYSE-Group-Announces-2025-2026-and-2027-Holiday-and-Early-Closings-Calendar/default.aspx
- https://ir.theice.com/press/news-details/2024/NYSE-Group-Announces-2024-2025-and-2026-Holiday-and-Early-Closings-Calendar/default.aspx

Crypto, including BTC-USD, uses every UTC day `[00:00, next 00:00)`, including weekends and leap days. The latest completed day is always the preceding UTC date. At an exact close boundary a session is completed. No publication-delay grace period is inferred: absent data after that boundary is unavailable, and retrying later can recover. Daily labels must already be normalized to the stated convention by an audited provider adapter; this module does not guess labels from arbitrary timestamps.

## Provenance, archives and trust

Each frozen snapshot includes symbol, market, source URL, retrieval/as-of timestamps, window, timezone, session convention, calendar/schema versions, adjustment basis, code version, dependency version pairs, evidence classification and immutable daily records. The v1 source endpoint is the exact Yahoo chart URL for the URL-encoded symbol (`endpoint(symbol)`); other endpoints/providers require a reviewed schema extension. Store the original provider response separately if independently verifying upstream bytes; the hash here authenticates the normalized snapshot only. Dependency metadata must describe the actual producer (Python, provider library, pandas and timezone database/system image as applicable); it is not a dependency lockfile or proof of the claimed versions.

`canonical(snapshot)` serializes sorted-key compact UTF-8 JSON with a final newline, rejecting NaN/Infinity. `digest` is its SHA-256, covering records **and metadata**. `save` creates `<sha256>.json` exclusively and refuses conflicting bytes at an existing name; changed inputs produce a different path. `load` verifies the filename hash, schema, full eligibility and canonical bytes. The content hash is in the filename, outside its own payload. Never overwrite an existing archive. Storage permissions/version control provide durability; a hash is integrity evidence, not provider authenticity, a signature, or tamper-proof storage. Old snapshots remain eligible for their recorded as-of, not automatically for today's clock. Monitoring must supply/revalidate a new as-of and compare source sessions, rather than rely on file modification time.

## Adjustment and corporate-action limits

Existing stock/crypto paper traders use Yahoo `Close` with `auto_adjust=False` (raw closes), while `strategy_comparison.py` uses `auto_adjust=True` (adjusted closes). These can differ around splits and dividends; comparison outputs cannot be reconciled to saved paper prices merely by matching dates. v1 requires `raw_close` or `adjusted_close` explicitly and rejects comparisons mixing them. Do not relabel old files as adjusted, rewrite paper history, infer dividends/split factors, or claim a total-return benchmark from raw prices. Adjusted histories may be revised by the vendor; new retrievals must create new snapshots. A future corporate-action adapter and consumer integration require separate review.

## Checked-in evidence

`fixtures.json` indexes content-addressed SPY, ETH-USD and BTC-USD snapshots. These are **synthetic illustrative fixtures**, with invented prices and clocks, not downloaded market data, historical backtest results or simulated live paper records. Their source URLs describe the endpoint contract and do not assert a fetch occurred. They demonstrate archive/consumer behavior offline. No genuine provider snapshot is claimed: the legacy CSVs lack sufficient provenance to certify retrospectively. A caller with an independently retrieved feed can construct and archive historical research snapshots through the same API; this task introduces no downloader or network dependency.

## Verification

Deterministic tests: `python -m unittest discover -s tests -p test_dataset_contracts.py -v`.
Run the handbook full unittest and compile checks as well. Tests cover close/UTC/DST boundaries, holidays/early closes, missing endpoints/interior sessions, stale retrievals, invalid prices/dates, duplicates/order, comparison metadata, immutability, endpoint identity and archive hash corruption. No profitability or human acceptance is inferred from passing tests.
