# Editorial redesign review

References: the owner's Pinterest editorial screenshot and Kaitlyn's Trading dashboard mockup supplied in chat. Cream, beige, taupe and espresso replace the pink dashboard; self-hosted Cormorant Garamond and Great Vibes supply the serif and script accents. Font licenses are in `docs/fonts/`.

| Viewport | Before | After |
| --- | --- | --- |
| Desktop, 1440px | [Before](before-1440.png) | [After](after-1440.png) |
| Mobile, 375px | [Before](before-375.png) | [After](after-375.png) |

These images show saved simulated paper records, not real trading results. The mockup's illustrative $100,000 balance is never used. Before markup is fixed to commit `402a308837bfc7256af6fc4da9f159bfdf30f63b`; both versions load the same local saved CSVs. External embedded charts are stubbed for deterministic offline review.

## Behavior

- Overview: welcome, four compact saved metrics, one equity chart, three feature links.
- Markets: existing stock/crypto and educational chart tools, including Volume Profile.
- AI Copilot: existing evidence gates, local screenshot intake and simulation disclosures.
- Strategy Lab: existing hypothesis, comparison, discovery and scenario tools.
- Account Health: statuses, report downloads, profit breakdown, data checks and journal.
- Settings: concise read-only account explanation; no invented controls or connected account.
- Hash routes support GitHub Pages, direct legacy section links, keyboard use and Back. Without JavaScript, original content remains available with native fallback links.

All existing data loading, calculations and research modules remain intact. Existing nodes are moved rather than copied, retaining IDs and event listeners. No data artifacts, trading rules or account balances are changed.

## Validation

Run `python tests/editorial_browser.py` with Playwright 1.62.0 and its Chromium installed. It captures the four images and checks saved Stocks/Crypto balances, dates, six views, keyboard/deep-link/Back behavior, five widths (320–1440px), 44px controls, chart interactions, and failed-data navigation. The existing dashboard test additionally checks seven widths and the no-JavaScript fallback. CI runs both suites plus existing discovery, profile, health and Copilot checks.

Local checks used Playwright 1.62.0 with the explicit `/usr/bin/chromium` override (Chromium 154). Copilot visual baselines intentionally change with this redesign. The committed baselines come from canonical CI run `42152153215` in the repository's pinned image (Chromium 151.0.7922.34), after review of its screenshots; local Chromium 154 differs in emoji rendering and one pixel of panel height. The strict size and 0.1% pixel thresholds remain unchanged.

Related phase issue: #4 — “Navigation sidebar”, “Stocks, Crypto, Research and Reports sections”, and “Mobile layout and accessibility”. Checklist completion remains pending human review and merge.
