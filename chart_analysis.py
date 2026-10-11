"""Read-only technical chart analysis for the stock research bot.

Uses daily OHLCV market data and writes measurements only. It does not place trades
or alter the paper portfolio.
"""
import os
import math
import pandas as pd
import yfinance as yf
TICKERS=["AAPL","MSFT","NVDA","AMZN"];OUT="paper/chart_analysis.csv"
def col(df,name):
 x=df[name]
 if hasattr(x,"columns"):x=x.iloc[:,0]
 return x.astype(float)
def analyze(t):
 d=yf.download(t,period="2y",interval="1d",auto_adjust=False,progress=False)
 if d.empty or len(d)<200:return None
 close=col(d,"Close");high=col(d,"High");low=col(d,"Low");vol=col(d,"Volume")
 delta=close.diff();gain=delta.clip(lower=0).rolling(14).mean();loss=(-delta.clip(upper=0)).rolling(14).mean();rs=gain/loss.replace(0,float("nan"));rsi=100-(100/(1+rs))
 ema12=close.ewm(span=12,adjust=False).mean();ema26=close.ewm(span=26,adjust=False).mean();macd=ema12-ema26;macds=macd.ewm(span=9,adjust=False).mean()
 ma20=close.rolling(20).mean();ma50=close.rolling(50).mean();ma200=close.rolling(200).mean()
 support=low.iloc[-20:].min();resistance=high.iloc[-20:].max();vavg=vol.rolling(20).mean().iloc[-1]
 price=float(close.iloc[-1]);rv=float(rsi.iloc[-1]);trend="UP" if price>ma200.iloc[-1] and ma20.iloc[-1]>ma50.iloc[-1] else ("DOWN" if price<ma200.iloc[-1] and ma20.iloc[-1]<ma50.iloc[-1] else "MIXED")
 momentum="POSITIVE" if macd.iloc[-1]>macds.iloc[-1] else "NEGATIVE";volume_ratio=vol.iloc[-1]/vavg if vavg else 0
 if not math.isfinite(price) or price<=0 or not math.isfinite(rv):return None
 score=50+(15 if trend=="UP" else -15 if trend=="DOWN" else 0)+(10 if momentum=="POSITIVE" else -10)+(5 if 50<=rv<=70 else -5 if rv>75 or rv<30 else 0)+(5 if volume_ratio>=1.2 else 0)
 return {"market_session":close.index[-1].date().isoformat(),"ticker":t,"close":round(price,4),"trend":trend,"rsi14":round(rv,2),"macd":round(macd.iloc[-1],4),"macd_signal":round(macds.iloc[-1],4),"momentum":momentum,"support_20d":round(support,4),"resistance_20d":round(resistance,4),"volume_vs_20d":round(volume_ratio,3),"evidence_score":max(0,min(100,score))}
def main():
 rows=[x for x in (analyze(t) for t in TICKERS) if x]
 os.makedirs("paper",exist_ok=True)
 if rows:pd.DataFrame(rows).to_csv(OUT,index=False)
 print("CHART ANALYSIS — RESEARCH ONLY");print(pd.DataFrame(rows).to_string(index=False) if rows else "No complete data.");print("No trades were placed.")
if __name__=="__main__":main()
