"""Data-integrity gate for smart-money research outputs.

Research only. Detects suspicious/malformed evidence before downstream statistics
are treated as trustworthy. It never controls wallets or executes transactions.
"""
import csv,json,math,os
from datetime import datetime,timezone
D="smart_money";REPORT=os.path.join(D,"integrity_report.txt");STATE=os.path.join(D,"integrity_status.json")
def rows(name):
 p=os.path.join(D,name)
 if not os.path.exists(p):return []
 try:
  with open(p,newline="",encoding="utf-8") as f:return list(csv.DictReader(f))
 except Exception:return []
def num(v):
 try:return float(v)
 except (TypeError,ValueError):return None
def time(v):
 try:
  d=datetime.fromisoformat((v or "").replace("Z","+00:00"))
  return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
 except Exception:return None
def main():
 os.makedirs(D,exist_ok=True);obs=rows("observations.csv");outs=rows("outcomes.csv");issues=[]
 ids=[r.get("observation_id","") for r in obs]
 dup={x for x in ids if x and ids.count(x)>1}
 for x in sorted(dup):issues.append(("ERROR","duplicate_observation",x))
 for i,r in enumerate(obs,1):
  oid=r.get("observation_id","") or "row-"+str(i);p=num(r.get("entry_price_usd"));t=time(r.get("observed_at_utc"))
  if not oid:issues.append(("ERROR","missing_observation_id","row-"+str(i)))
  if p is None or not math.isfinite(p) or p<=0:issues.append(("ERROR","invalid_entry_price",oid))
  if not t:issues.append(("ERROR","invalid_observed_time",oid))
  elif t>datetime.now(timezone.utc):issues.append(("ERROR","future_observation_time",oid))
 keys=[]
 for i,r in enumerate(outs,1):
  oid=r.get("observation_id","");h=r.get("horizon_hours","");key=(oid,h);keys.append(key);ret=num(r.get("return_pct"));entry=num(r.get("entry_price_usd"));out=num(r.get("outcome_price_usd"));elapsed=num(r.get("actual_elapsed_hours"));target=num(h)
  label=oid or "outcome-row-"+str(i)
  if not oid or not h:issues.append(("ERROR","missing_outcome_key",label))
  if entry is None or entry<=0 or out is None or out<=0:issues.append(("ERROR","invalid_outcome_price",label))
  if ret is None or not math.isfinite(ret):issues.append(("ERROR","invalid_return",label))
  elif ret<=-100:issues.append(("ERROR","impossible_return_below_minus_100",label))
  elif abs(ret)>10000:issues.append(("WARN","extreme_return_over_100x",label))
  if elapsed is not None and target is not None and elapsed+0.01<target:issues.append(("ERROR","outcome_recorded_before_target",label))
 seen=set()
 for k in keys:
  if k in seen and k!=("",""):issues.append(("ERROR","duplicate_outcome",str(k)))
  seen.add(k)
 errors=sum(x[0]=="ERROR" for x in issues);warns=sum(x[0]=="WARN" for x in issues);status="BLOCKED" if errors else ("WARNING" if warns else "OK")
 report=["SMART-MONEY DATA INTEGRITY REPORT","Research only — no transactions or wallet control.","",f"Observations checked: {len(obs)}",f"Outcomes checked: {len(outs)}",f"Status: {status}",f"Errors: {errors}",f"Warnings: {warns}",""]
 report += [f"{a}: {b} — {c}" for a,b,c in issues] if issues else ["No integrity anomalies detected."]
 with open(REPORT,"w",encoding="utf-8") as f:f.write("\n".join(report)+"\n")
 with open(STATE,"w",encoding="utf-8") as f:json.dump({"status":status,"errors":errors,"warnings":warns,"observations_checked":len(obs),"outcomes_checked":len(outs)},f,indent=2)
 print("\n".join(report))
 if errors:raise SystemExit("Integrity gate blocked downstream research statistics.")
if __name__=="__main__":main()
