"""Forward outcome tracker for chart-analysis snapshots. Research only."""
import csv,os
import pandas as pd
import yfinance as yf
SNAP="paper/chart_analysis.csv";HIST="paper/chart_analysis_history.csv";OUT="paper/chart_outcomes.csv";H=[1,5,20]
def load(p):
 if not os.path.exists(p):return []
 with open(p,newline="",encoding="utf-8") as f:return list(csv.DictReader(f))
def append_unique_history():
 rows=load(SNAP);old=load(HIST);keys={(r.get("market_session"),r.get("ticker")) for r in old};new=[r for r in rows if (r.get("market_session"),r.get("ticker")) not in keys]
 if new:
  pd.DataFrame(new).to_csv(HIST,mode="a",header=not os.path.exists(HIST),index=False)
 return len(new)
def main():
 os.makedirs("paper",exist_ok=True);added=append_unique_history();hist=load(HIST);out=load(OUT);done={(r.get("market_session"),r.get("ticker"),r.get("horizon_sessions")) for r in out};new=[]
 for r in hist:
  ticker=r.get("ticker");start=r.get("market_session");entry=float(r.get("close",0) or 0)
  if not ticker or not start or entry<=0:continue
  d=yf.download(ticker,period="1y",interval="1d",auto_adjust=False,progress=False)
  c=d["Close"];c=c.iloc[:,0] if hasattr(c,"columns") else c;c=c.dropna()
  dates=[x.date().isoformat() for x in c.index]
  if start not in dates:continue
  i=dates.index(start)
  for h in H:
   k=(start,ticker,str(h))
   if k in done or i+h>=len(c):continue
   price=float(c.iloc[i+h]);new.append({"market_session":start,"ticker":ticker,"horizon_sessions":h,"outcome_session":dates[i+h],"entry_close":entry,"outcome_close":round(price,4),"return_pct":round((price/entry-1)*100,4),"trend":r.get("trend",""),"rsi14":r.get("rsi14",""),"momentum":r.get("momentum",""),"volume_vs_20d":r.get("volume_vs_20d",""),"evidence_score":r.get("evidence_score","")});done.add(k)
 if new:pd.DataFrame(new).to_csv(OUT,mode="a",header=not os.path.exists(OUT),index=False)
 print(f"Chart snapshots added: {added}; new forward outcomes: {len(new)}");print("Research only — no trades were placed.")
if __name__=="__main__":main()
