"""Render a standalone, escaped research dashboard from the offline report."""
import argparse
from html import escape
from pathlib import Path
from .lab import load


def render(report):
    e = lambda v: escape(str(v), quote=True)
    rows = []
    for item in sorted(report['candidates'], key=lambda item: -item['quality']['score']):
        c, q = item['candidate'], item['quality']
        evidence = ''.join('<li>'+e(field)+': '+e(r['quote'])+' ('+e(r['start'])+'–'+e(r['end'])+'s)</li>' for field, records in c['evidence'].items() for r in records)
        unresolved = ''.join('<li>'+e(u)+'</li>' for u in c['uncertainties']) or '<li>No parser uncertainties; human review still required.</li>'
        rows.append('<article><h2>'+e(c['source']['title'])+'</h2><p><strong>'+e(q['grade'])+'</strong> · Research score '+e(q['score'])+'/100</p><p>Completeness '+e(q['completeness'])+' · Unresolved '+e(q['unresolved'])+' · Sensitivity stability '+e(q['stability'])+'</p><details><summary>Source evidence and review</summary><p>'+e(c['source']['video_url'])+'</p><p>Transcript permission: '+e(c['source']['permission']['reference'])+'</p><p>Source SHA-256: <code>'+e(c['source_sha256'])+'</code></p><ul>'+evidence+'</ul><h3>Uncertainty</h3><ul>'+unresolved+'</ul><p>Review is performed in the repository, bound to a candidate hash. This preview grants no approval.</p></details></article>')
    metrics = report['result']['periods']['evaluation']
    comparisons = [('Candidate', metrics['candidate']['return_pct'], metrics['candidate']['max_drawdown_pct']),
                   ('Cash', 0, 0), ('Buy and hold', metrics['baselines']['buy_hold']['return_pct'], metrics['baselines']['buy_hold']['max_drawdown_pct']),
                   ('Existing current 20/50', metrics['baselines']['existing_current_20_50']['return_pct'],metrics['baselines']['existing_current_20_50']['max_drawdown_pct']),
                   ('Existing trend (full exposure)',metrics['baselines']['existing_trend']['trend_return_pct'],metrics['baselines']['existing_trend']['trend_max_drawdown_pct']),
                   ('Existing momentum (full exposure)',metrics['baselines']['existing_momentum']['momentum_return_pct'],metrics['baselines']['existing_momentum']['momentum_max_drawdown_pct'])]
    table=''.join('<tr>'+''.join('<td>'+e(v)+'</td>' for v in (row[0],row[1],abs(row[2])))+'</tr>' for row in comparisons)
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Strategy Discovery Lab — synthetic preview</title>
<style>body{font:16px/1.6 system-ui;background:#101722;color:#e5ecf5;max-width:1100px;margin:auto;padding:32px}h1{font-size:2.5rem}article,section{background:#1b2637;border:1px solid #53657c;border-radius:12px;padding:24px;margin:24px 0}.notice{border-left:5px solid #f4c66c;padding:16px;background:#332c20}code{overflow-wrap:anywhere}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:12px;border-bottom:1px solid #53657c}summary{cursor:pointer;color:#a8d7ff}summary:focus-visible{outline:3px solid #f4c66c}small{color:#c7d3e2}</style>
<main><p>KAITLYN’S TRADING · RESEARCH</p><h1>Strategy Discovery Lab</h1><p class="notice">Simulation only · Original synthetic transcripts and prices · No real video claims · No profitability evidence</p><p>Discover → inspect timestamped evidence → resolve uncertainty → human review → isolated specification → simulation → independent evaluation</p>
<section><h2>Research queue</h2><p>Ranked by completeness, reproducibility and sensitivity stability. Returns do not affect research score. Every candidate remains historically unvalidated.</p>'''+''.join(rows)+'''</section><section><h2>Synthetic held-out comparison</h2><p>'''+e(metrics['start'])+' through '+e(metrics['end'])+''' · 120 daily fixture observations</p><div style="overflow-x:auto"><table><caption>Illustrative results; exposure and timing differ as described below.</caption><thead><tr><th scope="col">Strategy</th><th scope="col">Return %</th><th scope="col">Drawdown %</th></tr></thead><tbody>'''+table+'''</tbody></table></div><p>Drawdown is shown as a positive loss magnitude for all strategies; original signed metrics are preserved in the JSON report. Full-exposure comparison rules use prior-close fills; candidate uses optimistic same-close fills and 15% maximum allocation. These differences prevent an apples-to-apples profitability claim.</p></section><section><h2>Evaluation gate</h2><p>'''+e(report['submission']['status'])+'''</p><ul>'''+''.join('<li>'+e(p)+'</li>' for p in report['submission']['prerequisites'])+'''</ul><p>No submission runs externally from this preview. Real human review and accepted data are required for future historical integration.</p></section><section><h2>Reproducibility and limitations</h2><p>Specification SHA-256: <code>'''+e(report['result']['spec_sha256'])+'''</code></p><ul>'''+''.join('<li>'+e(x)+'</li>' for x in report['result']['limitations'])+'''</ul></section></main></html>'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('report',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(render(load(a.report)),encoding='utf-8')


if __name__=='__main__':main()
