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
 from simulation_v2.runner import run
 for variant in VARIANTS:
  run('stock', account_id='forward-'+variant['name'], variant=variant)
if __name__=='__main__':main()
