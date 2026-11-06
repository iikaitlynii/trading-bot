/* Read-only, simulation-only accounting. Does not alter the independent health panel. */
(function (root) {
  'use strict';
  const MODEL = 'paper-execution-v2';
  function checked(payload) {
    if (!payload || payload.schema_version !== 2 || payload.simulation_only !== true || payload.model !== MODEL || !Array.isArray(payload.accounts)) throw Error('V2 evidence unavailable or invalid');
    if (new Set(payload.accounts.map(a => a.id)).size !== payload.accounts.length) throw Error('Duplicate v2 accounts');
    for (const a of payload.accounts) {
      if (!a || typeof a.id !== 'string' || typeof a.reason !== 'string' || !['BLOCKED','UNAVAILABLE','SAVED_SIMULATION'].includes(a.availability)) throw Error('Invalid v2 account evidence');
      if (a.availability === 'SAVED_SIMULATION' && (!a.accounting || !a.positions || !Array.isArray(a.pending_orders) || !Array.isArray(a.fills) || !a.assumptions || !/^[a-f0-9]{64}$/.test(a.generation))) throw Error('Incomplete v2 accounting evidence');
    }
    return payload.accounts;
  }
  function render(target, payload) {
    target.replaceChildren();
    const text = (parent, tag, value) => { const e = document.createElement(tag); e.textContent = value; parent.append(e); return e; };
    try {
      for (const a of checked(payload)) {
        const card = text(target, 'article', '');card.className = 'simulation-v2-account';
        text(card, 'h4', a.id + ' · ' + a.availability.replaceAll('_',' '));
        text(card, 'p', a.reason);
        if (a.availability !== 'SAVED_SIMULATION') continue;
        text(card, 'p', 'SIMULATION ONLY · Saved source session ' + a.last_session + ' · may be stale. Separate from legacy returns.');
        text(card, 'p', 'Cost assumptions (not verified market costs): fee ' + a.assumptions.fee_bps + ' bps + $' + a.assumptions.fixed_fee + ' per fill; adverse slippage ' + a.assumptions.slippage_bps + ' bps.');
        const labels = {cash:'Cash',cost_basis:'Open cost basis',realized_pnl:'Realized P/L',unrealized_pnl:'Unrealized P/L',fees:'Cumulative fees',total_equity:'Total equity'};
        for (const [key,label] of Object.entries(labels)) text(card, 'p', label + ': ' + (a.accounting[key] ?? 'unavailable'));
        if (a.risk && a.risk.limit_breach) text(card,'p','SIMULATED EXPOSURE WARNING: existing holdings exceed assumed limits.');
        if (a.risk && a.risk.drawdown_warning) text(card,'p','SIMULATED DRAWDOWN WARNING: threshold reached.');
        for (const [symbol,p] of Object.entries(a.positions)) text(card,'p',symbol + ': ' + p.units + ' units; cost basis ' + p.cost_basis);
        text(card, 'p', 'Pending simulated orders: ' + a.pending_orders.length);
        for (const o of a.pending_orders) text(card, 'p', o.side + ' ' + o.symbol + ' · signal ' + o.signal_session + ' · created ' + o.created_at + ' · budget ' + o.budget + ' · awaiting a later validated close');
        text(card,'p','Recorded simulated fills: '+a.fills.length);
        for (const f of a.fills.slice(-10)) text(card,'p',f.side+' '+f.symbol+' · '+f.session+' · '+f.units+' units at '+f.execution_price+' · assumed fee '+f.fee+' · assumed slippage cost '+f.slippage_cost);
      }
    } catch (error) { text(target, 'p', 'V2 accounting unavailable. No pending-order count, valuation or fill is inferred.'); }
  }
  if (typeof module === 'object' && module.exports) module.exports = {checked};
  if (root.document) {
    const start = () => { const target = document.getElementById('simulation-v2-rows'); if (target) fetch('simulation-v2/status.json',{cache:'no-store'}).then(r => {if(!r.ok) throw Error('Missing evidence');return r.json();}).then(p => render(target,p)).catch(() => render(target,null)); };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
  }
})(typeof globalThis === 'object' ? globalThis : this);
