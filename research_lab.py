import math
import os

import pandas as pd
import yfinance as yf

OUT_DIR = "research_lab"
LATEST_FILE = os.path.join(OUT_DIR, "latest_shadow_results.csv")
HISTORY_FILE = os.path.join(OUT_DIR, "shadow_history.csv")
REPORT_FILE = os.path.join(OUT_DIR, "report.txt")
STARTING = 10000.0
COMMISSION = 0.001
SLIPPAGE = 0.001

UNIVERSES = {
    "core4": ["AAPL", "MSFT", "NVDA", "AMZN"],
    "diversified16": ["AAPL","MSFT","NVDA","AMZN","GOOGL","META","JPM","XOM","WMT","KO","JNJ","UNH","CAT","HD","PG","CVX"],
}
VARIANTS = [
    {"name":"current_20_50","fast":20,"slow":50,"regime":200,"stop":0.04,"max_weight":0.20},
    {"name":"faster_10_30","fast":10,"slow":30,"regime":150,"stop":0.03,"max_weight":0.15},
    {"name":"conservative_30_75","fast":30,"slow":75,"regime":200,"stop":0.05,"max_weight":0.15},
    {"name":"low_concentration_20_50","fast":20,"slow":50,"regime":200,"stop":0.04,"max_weight":0.10},
]

def download_all():
    frames=[]
    for ticker in sorted({t for universe in UNIVERSES.values() for t in universe}):
        data=yf.download(ticker,period="10y",interval="1d",auto_adjust=False,progress=False)
        close=data["Close"]
        if hasattr(close,"columns"): close=close.iloc[:,0]
        frames.append(close.rename(ticker))
    return pd.concat(frames,axis=1)

def max_drawdown(values):
    peak=values[0]; worst=0.0
    for value in values:
        peak=max(peak,value); worst=max(worst,(peak-value)/peak if peak else 0.0)
    return worst*100

def run_variant(prices,cfg):
    warmup=max(cfg["regime"],cfg["slow"]); cash=STARTING; positions={}; entries={}; equity=[STARTING]
    wins=trades=0; gross_wins=gross_losses=0.0; hold_days=[]
    for i in range(warmup,len(prices)):
        row=prices.iloc[i]; account=cash+sum(positions[t]*float(row[t]) for t in positions)
        for ticker in list(positions):
            p=float(row[ticker]); series=prices[ticker]
            fast=float(series.iloc[i-cfg["fast"]+1:i+1].mean()); slow=float(series.iloc[i-cfg["slow"]+1:i+1].mean())
            regime=float(series.iloc[i-cfg["regime"]+1:i+1].mean()); entry=entries[ticker]
            if fast<slow or p<regime or p<=entry["price"]*(1-cfg["stop"]):
                proceeds=positions[ticker]*p*(1-SLIPPAGE)*(1-COMMISSION); pnl=proceeds-entry["cost"]; cash+=proceeds; trades+=1
                hold_days.append(i-entry["index"])
                if pnl>0: wins+=1; gross_wins+=pnl
                else: gross_losses+=abs(pnl)
                del positions[ticker]; del entries[ticker]
        account=cash+sum(positions[t]*float(row[t]) for t in positions)
        slots=max(0,int(1/cfg["max_weight"])-len(positions))
        if slots:
            candidates=[]
            for ticker in prices.columns:
                if ticker in positions: continue
                series=prices[ticker]; p=float(row[ticker])
                fast=float(series.iloc[i-cfg["fast"]+1:i+1].mean()); slow=float(series.iloc[i-cfg["slow"]+1:i+1].mean())
                regime=float(series.iloc[i-cfg["regime"]+1:i+1].mean())
                if p>regime and fast>slow:
                    candidates.append((p/float(series.iloc[max(0,i-63)])-1,ticker))
            for _,ticker in sorted(candidates,reverse=True)[:slots]:
                target=min(cash,account*cfg["max_weight"])
                if target<50: break
                p=float(row[ticker]); buy=p*(1+SLIPPAGE); shares=(target*(1-COMMISSION))/buy; cash-=target
                positions[ticker]=shares; entries[ticker]={"price":buy,"cost":target,"index":i}
        equity.append(cash+sum(positions[t]*float(row[t]) for t in positions))
    final=equity[-1]; total=(final/STARTING-1)*100; years=max((len(equity)-1)/252,1/252)
    cagr=((final/STARTING)**(1/years)-1)*100 if final>0 else -100
    daily=pd.Series(equity).pct_change().dropna(); sharpe=float(daily.mean()/daily.std()*math.sqrt(252)) if len(daily)>1 and daily.std() else 0
    start=prices.iloc[warmup]; end=prices.iloc[-1]; bench=sum(float(end[t]/start[t]-1) for t in prices.columns)/len(prices.columns)*100
    return {"ending_value":round(final,2),"return_pct":round(total,4),"cagr_pct":round(cagr,4),"max_drawdown_pct":round(max_drawdown(equity),4),
      "sharpe":round(sharpe,4),"completed_trades":trades,"win_rate_pct":round(wins/trades*100 if trades else 0,4),
      "profit_factor":round(gross_wins/gross_losses if gross_losses else (999 if gross_wins else 0),4),
      "avg_hold_days":round(sum(hold_days)/len(hold_days) if hold_days else 0,2),"benchmark_return_pct":round(bench,4),"excess_vs_benchmark_pct":round(total-bench,4)}

def main():
    os.makedirs(OUT_DIR,exist_ok=True); all_prices=download_all(); rows=[]
    for name,tickers in UNIVERSES.items():
        prices=all_prices[tickers].dropna()
        market_session=prices.index[-1].date().isoformat()
        for cfg in VARIANTS:
            result=run_variant(prices,cfg); rows.append({"market_session":market_session,"universe":name,"variant":cfg["name"],**result})
    df=pd.DataFrame(rows); df.to_csv(LATEST_FILE,index=False)
    # One history snapshot per completed market session + universe + variant.
    if os.path.exists(HISTORY_FILE):
        old=pd.read_csv(HISTORY_FILE)
        combined=pd.concat([old,df],ignore_index=True)
        keys=["market_session","universe","variant"]
        if all(k in combined.columns for k in keys): combined=combined.drop_duplicates(subset=keys,keep="last")
        combined.to_csv(HISTORY_FILE,index=False)
    else: df.to_csv(HISTORY_FILE,index=False)
    with open(REPORT_FILE,"w",encoding="utf-8") as f:
        f.write("PARALLEL SHADOW STRATEGY RESEARCH LAB\nSimulation/research only — no brokerage orders are sent.\n\n")
        f.write("Latest completed market session: "+str(df["market_session"].max())+"\n")
        f.write("Historical backtests are snapshots, not independent forward-test samples.\n")
        f.write("History stores at most one snapshot per market session/universe/variant.\n\n")
        f.write(df.to_string(index=False)+"\n")
    print(df.to_string(index=False)); print("\nSaved:",LATEST_FILE,HISTORY_FILE,REPORT_FILE)

if __name__=="__main__": main()
