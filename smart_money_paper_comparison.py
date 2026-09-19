"""Compare qualifying smart-money research signals with a neutral control.

Simulation/research only. This does not execute, recommend, or copy trades.
It summarizes already-recorded 24h forward outcomes and uses a deterministic
control sample from non-qualifying observations when available.
"""
import csv, os, hashlib, statistics

D="smart_money"; OBS=os.path.join(D,"observations.csv"); OUT=os.path.join(D,"outcomes.csv")
REPORT=os.path.join(D,"paper_comparison.txt"); CSV=os.path.join(D,"paper_comparison.csv")
COST_PCT=0.40  # conservative round-trip friction assumption for research comparison

def read(path):
    if not os.path.exists(path): return []
    with open(path,newline="",encoding="utf-8") as f:return list(csv.DictReader(f))
def f(v,d=0.0):
    try:return float(v)
    except (TypeError,ValueError):return d
def score(r):
    weights={"wallet_quality":.30,"wallet_consensus":.20,"social_confirmation":.15,
             "liquidity_quality":.15,"momentum_confirmation":.10,"risk_quality":.10}
    c={k:max(0,min(100,f(r.get(k)))) for k in weights}
    if c["liquidity_quality"]<40 or c["risk_quality"]<40:return 0,"REJECT"
    s=sum(c[k]*weights[k] for k in weights)
    return s,("HIGH_INTEREST" if s>=75 else "WATCH" if s>=60 else "LOW_INTEREST")
def metrics(vals):
    if not vals:return {"n":0,"avg":0,"win":0,"median":0}
    return {"n":len(vals),"avg":statistics.mean(vals),"win":sum(x>0 for x in vals)/len(vals)*100,"median":statistics.median(vals)}
def main():
    os.makedirs(D,exist_ok=True); obs=read(OBS); outs=read(OUT)
    byid={r.get("observation_id",""):r for r in obs}
    signal=[]; pool=[]
    for o in outs:
        if str(o.get("horizon_hours",""))!="24":continue
        r=byid.get(o.get("observation_id",""))
        if not r:continue
        _,label=score(r); net=f(o.get("return_pct"))-COST_PCT
        if label=="HIGH_INTEREST":signal.append(net)
        elif label in ("WATCH","LOW_INTEREST"):pool.append((o.get("observation_id",""),net))
    # Deterministic control avoids cherry-picking and stays reproducible.
    pool.sort(key=lambda x:hashlib.sha256(x[0].encode()).hexdigest())
    control=[x[1] for x in pool[:len(signal)]] if signal else []
    sm,cm=metrics(signal),metrics(control)
    fields=["group","samples","avg_net_return_pct","median_net_return_pct","win_rate_pct","assumed_round_trip_cost_pct"]
    rows=[
      {"group":"qualifying_signal","samples":sm["n"],"avg_net_return_pct":round(sm["avg"],4),"median_net_return_pct":round(sm["median"],4),"win_rate_pct":round(sm["win"],2),"assumed_round_trip_cost_pct":COST_PCT},
      {"group":"neutral_control","samples":cm["n"],"avg_net_return_pct":round(cm["avg"],4),"median_net_return_pct":round(cm["median"],4),"win_rate_pct":round(cm["win"],2),"assumed_round_trip_cost_pct":COST_PCT}]
    with open(CSV,"w",newline="",encoding="utf-8") as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(rows)
    enough=sm["n"]>=30 and cm["n"]>=30
    text=["SMART-MONEY PAPER VS CONTROL","Simulation/research only — no trades executed.","",
          f"Qualifying 24h samples: {sm['n']}",f"Control 24h samples: {cm['n']}",
          f"Qualifying avg net return: {sm['avg']:.4f}%",f"Control avg net return: {cm['avg']:.4f}%",
          f"Qualifying win rate: {sm['win']:.2f}%",f"Control win rate: {cm['win']:.2f}%","",
          "EVIDENCE STATUS: "+("FIRST COMPARISON AVAILABLE" if enough else "TOO EARLY — keep collecting forward outcomes."),
          "This comparison is descriptive and does not predict future profits."]
    with open(REPORT,"w",encoding="utf-8") as fh:fh.write("\n".join(text)+"\n")
    print("\n".join(text))
if __name__=="__main__":main()
