"""True forward shadow accounts for fixed stock-strategy variants.

Simulation only. Each variant keeps independent state and advances once per actual
completed market session. No brokerage connection or order submission exists.
"""
import csv,json,os
import pandas as pd
import yfinance as yf

D="research_lab/forward"; STATE=os.path.join(D,"state.json"); PERF=os.path.join(D,"performance.csv")
START=10000.0; TICKERS=["AAPL","MSFT","NVDA","AMZN"]
VARIANTS=[
 {"name":"current_20_50","fast":20,"slow":50,"regime":200,"stop":.04,"weight":.20},
 {"name":"faster_10_30","fast":10,"slow":30,"regime":150,"stop":.03,"weight":.15},
 {"name":"conservative_30_75","fast":30,"slow":75,"regime":200,"stop":.05,"weight":.15},
 {"name":"low_concentration_20_50","fast":20,"slow":50,"regime":200,"stop":.04,"weight":.10}]
def load():
 if os.path.exists(STATE):
  with open(STATE,encoding="utf-8") as f:return json.load(f)
 return {v["name"]:{"cash":START,"positions":{},"last_session":None} for v in VARIANTS}
def prices():
 out={}
 for t in TICKERS:
  d=yf.download(t,period="2y",interval="1d",auto_adjust=False,progress=False); c=d["Close"]
  if hasattr(c,"columns"):c=c.iloc[:,0]
  out[t]=c.dropna()
 return out
def main():
 os.makedirs(D,exist_ok=True); state=load(); data=prices()
 dates={t:s.index[-1].date().isoformat() for t,s in data.items()}
 if len(set(dates.values()))!=1: print("Session mismatch",dates);return
 session=next(iter(set(dates.values()))); rows=[]
 for cfg in VARIANTS:
  s=state[cfg["name"]]
  if s.get("last_session")==session: continue
  market={t:float(data[t].iloc[-1]) for t in TICKERS}
  signals={}
  for t,c in data.items():
   if len(c)<cfg["regime"]:continue
   p=market[t]; fast=float(c.iloc[-cfg["fast"]:].mean()); slow=float(c.iloc[-cfg["slow"]:].mean()); regime=float(c.iloc[-cfg["regime"]:].mean())
   signals[t]=(p>regime and fast>slow)
  for t in list(s["positions"]):
   pos=s["positions"][t]; p=market[t]
   if not signals.get(t,False) or p<=float(pos["entry_price"])*(1-cfg["stop"]):
    s["cash"]+=float(pos["shares"])*p; del s["positions"][t]
  value=float(s["cash"])+sum(float(p["shares"])*market[t] for t,p in s["positions"].items())
  for t in TICKERS:
   if not signals.get(t,False) or t in s["positions"]:continue
   amount=min(float(s["cash"]),value*cfg["weight"])
   if amount<50:continue
   shares=amount/market[t];s["cash"]-=amount;s["positions"][t]={"shares":shares,"entry_price":market[t],"entry_session":session}
  value=float(s["cash"])+sum(float(p["shares"])*market[t] for t,p in s["positions"].items())
  s["last_session"]=session
  rows.append({"market_session":session,"variant":cfg["name"],"paper_value":round(value,2),"cash":round(float(s["cash"]),2),"open_positions":len(s["positions"]),"total_return_pct":round((value/START-1)*100,4)})
 with open(STATE,"w",encoding="utf-8") as f:json.dump(state,f,indent=2,sort_keys=True)
 if rows:
  exists=os.path.exists(PERF)
  with open(PERF,"a",newline="",encoding="utf-8") as f:
   w=csv.DictWriter(f,fieldnames=list(rows[0])); 
   if not exists:w.writeheader()
   w.writerows(rows)
 print("TRUE FORWARD SHADOW ACCOUNTS — SIMULATION ONLY");print("Market session:",session);print("Accounts advanced:",len(rows))
 for r in rows:print(r["variant"],"$"+str(r["paper_value"]),str(r["total_return_pct"])+"%")
if __name__=="__main__":main()
