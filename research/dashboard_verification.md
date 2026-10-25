# Dashboard navigation, reflow and accessibility verification

Relates to issue #4, exact items: **Navigation sidebar**; **Stocks, Crypto, Research and Reports sections**; **Mobile layout and accessibility**. Checkboxes remain subject to human review after merge.

The desktop sidebar links to portfolio overview, Stocks, Crypto, Research, Reports and trade history. On narrow screens the same links form a compact grid. Native fragments preserve deep links and browser history; no panel is hidden or removed. The existing portfolio buttons still select saved stock or crypto account data independently of research navigation. A visible status names the selected portfolio.

Accessibility changes include a first-focus skip link, visible focus indicators for links and form controls, focusable section destinations, current-location navigation semantics, 44px minimum control heights, column header scopes, and named keyboard-focusable table scroll regions. Small screens use a single metric column; long text wraps and wide tables scroll within their panels.

## Automated checks performed

- `python -m unittest discover -s tests -v`: **3 tests passed**, using `/workspace/.venvs/trading-bot/bin/python` with the existing requirements installed. The default interpreter initially failed because `yfinance` was absent; that failed run is not counted as a pass.
- `python -m compileall -q paper_trader.py crypto_paper_trader.py strategy_comparison.py`: **passed** using the same interpreter.
- `node --check docs/dashboard.js`: **passed**.
- `python tests/dashboard_browser.py`: **passed** with Playwright and system Chromium. This optional standalone test is separate from unittest discovery. Install Playwright in a development environment and provide Chromium at `/usr/bin/chromium` to reproduce it. The test serves `docs/` locally and intercepts requests for saved CSVs with repository fixtures; it does not contact market providers. Local server/browser execution requires an environment permitting loopback sockets.

Browser assertions cover:

- All 19 original dashboard panel headings remain present.
- Stocks and Crypto toggles retain pressed states, name the selected account, and render the last saved portfolio values.
- Keyboard activation of the skip link and all six navigation links moves focus to the destination; current-link state follows fragments and browser Back.
- No document-wide horizontal overflow at widths **320, 375, 480, 640, 768, 1024, 1440** CSS pixels. The 640px case also exercises the effective viewport width of a 1280px window at 200% zoom; it is not a separate browser zoom test.
- Visible navigation links, buttons, selects and inputs have at least 44px height at each width.
- A data table scrolls horizontally using ArrowRight while focused; every table column header has `scope="col"`.
- Stock symbol selection, quarterly scenario input, watch-score and crypto-liquidity filters, and weekly report rows remain functional.
- No uncaught JavaScript errors during the normal-data checks.
- Reports navigation remains keyboard-accessible after a simulated 503 portfolio-data failure.
- Reports links still navigate with JavaScript disabled.

Desktop (1440px) and mobile (375px) screenshots were inspected visually. Re-running the browser script saves those views under `work/`, outside the committed source.

## Scope and limits

This is a UI change only. No trading-engine files, CSV snapshots, portfolio calculations, workflows, or roadmap statuses are changed. Results shown by the dashboard remain **saved simulated paper records**, **historical hypothetical backtests**, or explicitly labeled **illustrative planning estimates** as before. No brokerage or exchange execution is introduced.

The TradingView iframe is replaced with a local placeholder in automated tests, so third-party widget rendering and live network availability were not verified. Clipboard permissions, PDF/CSV export additions, monthly/yearly reporting additions, and a full screen-reader or WCAG audit are outside this change. Browser checks are targeted accessibility regression evidence, not an accessibility certification.
