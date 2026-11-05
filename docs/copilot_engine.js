/* Deterministic teaching rules, shared by the offline producer and dashboard. */
(function(root) {
  'use strict';
  const charts = typeof module !== 'undefined' && module.exports ? require('./chart_intelligence.js') : root.ChartIntelligence;
  const RULE = 'copilot-sma-rsi-v1';
  const LABELS = {BUY:'↑ BUY SETUP',SELL:'↓ SELL SETUP',WAIT:'⏸ WAIT'};
  function assess(input, now = Date.now()) {
    const out = {state:'WAIT',label:LABELS.WAIT,explanation:'No verified, complete market evidence is available.',
      conditions:[],uncertainty:'Technical patterns can fail. No accuracy or profitability has been established.',
      invalidation:'Missing, stale or unverified data invalidates every directional setup.',indicators:null};
    try {
      if (!input || input.schema_version !== 1 || input.rule !== RULE || !['AAPL','MSFT','NVDA','AMZN'].includes(input.symbol) || input.timeframe !== '1d') throw Error('Unsupported evidence or symbol/timeframe');
      if (input.quality !== 'VERIFIED' || input.evidence !== 'validated-provider-snapshot' || !/^[a-f0-9]{64}$/.test(input.bundle_sha256 || '')) throw Error(input.reason || 'Incomplete or unverified evidence');
      const created = Date.parse(input.observed_at), until = Date.parse(input.valid_until), source = Date.parse(input.source_timestamp);
      if (![created,until,source,now].every(Number.isFinite) || source > created || created > now || until <= now || until <= created) throw Error('Stale, future or missing timestamps');
      const bars = input.bars;
      if (!Array.isArray(bars) || bars.length < 51 || bars.length > 5000) throw Error('Insufficient verified history');
      let previous = '';
      for (const b of bars) {
        if (typeof b.session !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(b.session) || !Number.isFinite(Date.parse(b.session)) || new Date(b.session).toISOString().slice(0,10)!==b.session || b.session <= previous ||
          !['close','high','low','volume'].every(k=>typeof b[k]==='number' && Number.isFinite(b[k])) || b.low <= 0 || b.low > b.close || b.close > b.high || b.volume <= 0) throw Error('Malformed or incomplete bars');
        previous = b.session;
      }
      if (bars.at(-1).session !== input.source_session) throw Error('Source session mismatch');
      // Existing Market Intelligence deliberately uses the prior completed bar.
      const values = charts.indicators(bars), c = charts.confluence(bars, values), v = values.at(-2);
      if (!v || [v.sma20,v.sma50,v.rsi14,v.atr14,v.bandLow,v.bandHigh].some(x=>!Number.isFinite(x)) || c.missing) throw Error('Missing indicator evidence');
      out.indicators = v;
      out.conditions = c.evidence.map(e=>`${e.name}: ${e.state} — ${e.reason}`);
      out.conditions.push(`Setup uses completed session ${c.asof}; latest verified context ${input.source_session}.`);
      out.state = c.signal === 'SIMULATED LONG SETUP' ? 'BUY' : c.signal === 'SIMULATED DEFENSIVE SETUP' ? 'SELL' : 'WAIT';
      out.label = LABELS[out.state];
      out.explanation = out.state === 'BUY' ? 'The shorter trend average is above the longer average, and momentum is bullish. This is a hypothetical paper setup.' :
        out.state === 'SELL' ? 'The shorter trend average is below the longer average, and momentum is bearish. This is hypothetical defensive paper context; no short order is created.' : 'Trend and momentum do not agree on a clear paper setup.';
      out.invalidation = out.state === 'BUY' ? 'Invalid if SMA20 is no longer above SMA50, RSI14 falls to 55 or below, or data quality fails.' : out.state === 'SELL' ?
        'Invalid if SMA20 is no longer below SMA50, RSI14 rises to 45 or above, or data quality fails.' : 'Wait for verified, current data and agreement between trend and momentum.';
    } catch(error) { out.explanation = 'WAIT — '+error.message+'.'; }
    return out;
  }
  const api={RULE,LABELS,assess};
  if(typeof module!=='undefined'&&module.exports) module.exports=api; else root.CopilotEngine=api;
})(typeof globalThis!=='undefined'?globalThis:this);
