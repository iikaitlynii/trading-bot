"""Forward outcome tracker for smart-money research — simulation only.

A horizon means the first scheduled checkpoint after that target, not an exact
historical price at precisely 1h/24h/7d. Actual elapsed time is recorded so later
analysis can measure timing error instead of pretending the checkpoint was exact.
"""
import csv,json,os,urllib.parse,urllib.request
from datetime import datetime,timezone
D="smart_money";OBS=os.path.join(D,"observations.csv");OUT=os.path.join(D,"outcomes.csv")
URL="https://api.dexscreener.com/latest/dex/tokens/{}";HORIZONS=[1,24,168]
FIELDS=["observation_id","source_label","token","contract","network","observed_at_utc","evaluated_at_utc","horizon_hours","actual_elapsed_hours","checkpoint_delay_hours","entry_price_usd","outcome_price_usd","return_pct","profitable","dex","pair_address","liquidity_usd"]
def parse(v):
 if not v:return None
 dt=datetime.fromisoformat(v.replace("Z","+00:00"))
 return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
def num(v):
 try:return float(v)
 except (TypeError,ValueError):return None
def load(p):
 if not os.path.exists(p):return []
 with open(p,newline="",encoding="utf-8") as f:return list(csv.DictReader(f))
def oid(r):
 return r.get("observation_id","").strip() or "|".join([r.get("observed_at_utc",""),r.get("source_label",r.get("wallet_label","unknown")),r.get("contract",r.get("mint",""))])
def price(contract):
 req=urllib.request.Request(URL.format(urllib.parse.quote(contract,safe="")),headers={"User-Agent":"trading-bot-research/1.0"})
 with urllib.request.urlopen(req,timeout=20) as resp:p=json.loads(resp.read().decode())
 usable=[]
 for pair in p.get("pairs") or []:
  px=num(pair.get("priceUsd"));liq=num((pair.get("liquidity") or {}).get("usd")) or 0
  if px and px>0:usable.append((liq,px,pair))
 if not usable:return None,None
 liq,px,pair=max(usable,key=lambda x:x[0])
 return px,{"dex":pair.get("dexId",""),"pair_address":pair.get("pairAddress",""),"liquidity_usd":round(liq,2)}
def main():
 os.makedirs(D,exist_ok=True);obs=load(OBS);existing=load(OUT);seen={(r.get("observation_id",""),r.get("horizon_hours","")) for r in existing};now=datetime.now(timezone.utc);new=[];cache={}
 if not obs:print("SMART-MONEY OUTCOME TRACKER: no observations available yet.");return
 for r in obs:
  i=oid(r);t=parse(r.get("observed_at_utc"));contract=(r.get("contract") or r.get("mint") or "").strip();entry=num(r.get("entry_price_usd"))
  if not t or not contract or not entry or entry<=0:continue
  elapsed=(now-t).total_seconds()/3600
  due=[h for h in HORIZONS if elapsed>=h and (i,str(h)) not in seen]
  if not due:continue
  if contract not in cache:
   try:cache[contract]=price(contract)
   except Exception as e:print("Price read failed for",contract,str(e));cache[contract]=(None,None)
  current,market=cache[contract]
  if current is None:continue
  ret=(current/entry-1)*100
  for h in due:
   new.append({"observation_id":i,"source_label":r.get("source_label",r.get("wallet_label","unknown")),"token":r.get("token","UNKNOWN"),"contract":contract,"network":r.get("network","solana"),"observed_at_utc":t.isoformat(),"evaluated_at_utc":now.isoformat(),"horizon_hours":h,"actual_elapsed_hours":round(elapsed,4),"checkpoint_delay_hours":round(elapsed-h,4),"entry_price_usd":entry,"outcome_price_usd":current,"return_pct":round(ret,4),"profitable":"YES" if ret>0 else "NO","dex":(market or {}).get("dex",""),"pair_address":(market or {}).get("pair_address",""),"liquidity_usd":(market or {}).get("liquidity_usd","")});seen.add((i,str(h)))
 if new:
  # Rewrite if an older schema exists, preserving prior rows and deriving elapsed time where possible.
  combined=[]
  for r in existing:
   x={k:r.get(k,"") for k in FIELDS}
   if not x["actual_elapsed_hours"]:
    a=parse(r.get("observed_at_utc"));b=parse(r.get("evaluated_at_utc"))
    if a and b:
     e=(b-a).total_seconds()/3600;x["actual_elapsed_hours"]=round(e,4)
     h=num(r.get("horizon_hours"));x["checkpoint_delay_hours"]=round(e-h,4) if h is not None else ""
   combined.append(x)
  combined.extend(new)
  with open(OUT,"w",newline="",encoding="utf-8") as f:w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(combined)
 print("SMART-MONEY FORWARD OUTCOME TRACKER");print("Simulation/research only — no trades were sent.");print("New checkpoint outcomes:",len(new));print("Actual elapsed time and checkpoint delay are recorded for every new outcome.")
if __name__=="__main__":main()
