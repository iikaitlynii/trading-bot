"""Measure smart-money signal decay across forward checkpoints.

Research only. Uses already-recorded simulated outcomes; no wallet control or trades.
"""
import csv,os,statistics
D="smart_money";OUT=os.path.join(D,"signal_decay.csv");REPORT=os.path.join(D,"signal_decay_report.txt")
H=[1,24,168]
def load(name):
 p=os.path.join(D,name)
 if not os.path.exists(p):return []
 with open(p,newline="",encoding="utf-8") as f:return list(csv.DictReader(f))
def f(v):
 try:return float(v)
 except:return None
def main():
 outcomes=load("outcomes.csv"); groups={h:[] for h in H}; delays={h:[] for h in H}
 for r in outcomes:
  try:h=int(float(r.get("horizon_hours","")))
  except:continue
  ret=f(r.get("return_pct"));delay=f(r.get("checkpoint_delay_hours"))
  if h in groups and ret is not None:groups[h].append(ret)
  if h in delays and delay is not None:delays[h].append(delay)
 rows=[]
 for h in H:
  vals=groups[h]; ds=delays[h]
  rows.append({"horizon_hours":h,"samples":len(vals),"avg_return_pct":round(statistics.mean(vals),4) if vals else "","median_return_pct":round(statistics.median(vals),4) if vals else "","win_rate_pct":round(sum(x>0 for x in vals)/len(vals)*100,4) if vals else "","avg_checkpoint_delay_hours":round(statistics.mean(ds),4) if ds else ""})
 with open(OUT,"w",newline="",encoding="utf-8") as out:
  w=csv.DictWriter(out,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 mature=all(r["samples"]>=30 for r in rows)
 lines=["SMART-MONEY SIGNAL DECAY REPORT","Research only — descriptive forward evidence, not a trading recommendation.","","This compares recorded outcomes across 1h, 24h, and 7d checkpoints.","Checkpoint delays are reported because measurements may occur after the target time.",""]
 for r in rows:lines.append(f'{r["horizon_hours"]}h: {r["samples"]} samples | avg {r["avg_return_pct"]}% | median {r["median_return_pct"]}% | win rate {r["win_rate_pct"]}% | avg delay {r["avg_checkpoint_delay_hours"]}h')
 lines += ["","STATUS: "+("COMPARISON READY (30+ samples at every horizon)" if mature else "TOO EARLY — collect at least 30 outcomes at every horizon before interpreting decay.")]
 with open(REPORT,"w",encoding="utf-8") as out:out.write("\n".join(lines)+"\n")
 print("\n".join(lines))
if __name__=="__main__":main()
