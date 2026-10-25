/* Generated reporting snapshots; independent of trading/dashboard calculations. */
(function () {
  'use strict';
  let generation = 0;
  const element = id => document.getElementById(id);
  const format = (v, percent = false) => v === null || v === undefined || !Number.isFinite(v)
    ? 'Unavailable' : percent ? v.toFixed(2) + '%' : new Intl.NumberFormat('en-US', {style: 'currency', currency: 'USD'}).format(v);
  async function loadReports(account) {
    const token = ++generation;
    const status = element('report-status'), metrics = element('report-metrics'), body = element('report-months');
    metrics.replaceChildren(); body.replaceChildren();
    status.textContent = 'Loading saved performance report…';
    for (const kind of ['daily', 'monthly', 'summary']) {
      const link = element('report-' + kind);
      link.hidden = true;
    }
    try {
      const response = await fetch('https://raw.githubusercontent.com/iikaitlynii/trading-bot/main/reports/' + account + '.json', {cache: 'no-store'});
      if (!response.ok) throw Error('HTTP ' + response.status);
      const report = await response.json();
      if (token !== generation) return;
      if (report.schema_version !== 1 || report.account !== account || !report.metrics || !Array.isArray(report.monthly) || !Array.isArray(report.warnings)) throw Error('Unsupported report format');
      const m = report.metrics;
      status.textContent = 'Simulated forward paper records · as of ' + (report.as_of || 'unavailable') + ' · generated ' + report.generated_at_utc + '. ' + report.warnings.join(' · ');
      const items = [
        ['Total portfolio change since launch', m.total_portfolio_change, false],
        ['Realized FIFO trade P/L, before fees', m.realized_pnl, false],
        ['Unrealized P/L from reconciled recorded equity', m.unrealized_pnl, false],
        ['Unreconciled change (not classified as unrealized)', m.unreconciled_change, false],
        ['Launch return / excess over zero-interest cash', m.total_return_pct, true],
        ['Zero-interest cash return (assumption)', m.cash_return_pct, true],
        ['Portfolio return over benchmark dates', m.comparison_return_pct, true],
        ['Buy-and-hold price return: ' + report.benchmark.symbols.join(', '), report.benchmark.return_pct, true],
        ['Excess vs buy-and-hold (percentage points)', m.excess_vs_buy_hold_pct, true],
        ['Maximum recorded drawdown incl. launch capital', m.max_drawdown_pct, true]
      ];
      for (const [label, value, percent] of items) {
        const term = document.createElement('dt'), detail = document.createElement('dd');
        term.textContent = label; detail.textContent = format(value, percent);
        metrics.append(term, detail);
      }
      const note = document.createElement('p');
      note.textContent = 'Benchmark dates: ' + (report.start_date || 'unavailable') + ' to ' + (report.as_of || 'unavailable') + '. ' + report.benchmark.basis + '. Source: ' + report.benchmark.source + '. ' + report.benchmark.provenance;
      metrics.appendChild(note);
      for (const row of report.monthly) {
        const tr = document.createElement('tr');
        for (const value of [row.month, row.as_of, format(row.opening_value), format(row.closing_value), format(row.portfolio_change), format(row.return_pct, true), row.coverage]) {
          const td = document.createElement('td'); td.textContent = value; tr.appendChild(td);
        }
        body.appendChild(tr);
      }
      for (const kind of ['daily', 'monthly', 'summary']) {
        const link = element('report-' + kind);
        link.href = 'https://raw.githubusercontent.com/iikaitlynii/trading-bot/main/reports/' + account + '_' + kind + '.csv';
        link.download = account + '_' + kind + '.csv'; link.hidden = false;
      }
    } catch (error) {
      if (token === generation) status.textContent = 'Saved performance report unavailable: ' + error.message;
    }
  }
  for (const account of ['stocks', 'crypto']) element(account).addEventListener('click', () => loadReports(account));
  loadReports('stocks');
})();
