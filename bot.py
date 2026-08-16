import os
import sys
import math
import pandas as pd
import yfinance as yf

TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN"]
STARTING_MONEY = 10000
COMMISSION = 0.001
SLIPPAGE = 0.001
TRAIN_DAYS = 500
TEST_DAYS = 125
REGIME_MA_DAYS = 200
TRADING_DAYS = 252
MAX_STOCK_WEIGHT = 0.30
MIN_CASH_RESERVE = 0.10
RESULTS_DIR = "results"
RESULTS_FILE = os.path.join(RESULTS_DIR, "latest_results.txt")

CANDIDATES = [
    {"name":"MA 5/20","type":"ma","fast":5,"slow":20,"stop_loss":0.02},
    {"name":"MA 10/30","type":"ma","fast":10,"slow":30,"stop_loss":0.03},
    {"name":"MA 20/50","type":"ma","fast":20,"slow":50,"stop_loss":0.04},
    {"name":"Momentum 10d 3%","type":"momentum","lookback":10,"threshold":0.03,"stop_loss":0.02},
    {"name":"Momentum 20d 5%","type":"momentum","lookback":20,"threshold":0.05,"stop_loss":0.03},
    {"name":"Momentum 30d 7%","type":"momentum","lookback":30,"threshold":0.07,"stop_loss":0.04},
]

class Tee:
    def __init__(self,*streams): self.streams=streams
    def write(self,text):
        for s in self.streams: s.write(text); s.flush()
    def flush(self):
        for s in self.streams: s.flush()

def candidate_signals(prices,c):
    if c["type"]=="ma":
        fast=prices.rolling(c["fast"]).mean(); slow=prices.rolling(c["slow"]).mean()
        return fast>slow, fast<slow
    mom=prices.pct_change(c["lookback"])
    return mom>c["threshold"], mom<0

def simple_training_test(prices,c):
    buy,sell=candidate_signals(prices,c); regime=prices>prices.rolling(REGIME_MA_DAYS).mean()
    cash=1.0; shares=0.0; entry=0.0; values=[]; trades=0
    for i in range(REGIME_MA_DAYS,len(prices)):
        p=float(prices.iloc[i])
        if shares==0 and bool(buy.iloc[i]) and bool(regime.iloc[i]):
            bp=p*(1+SLIPPAGE); shares=(cash*(1-COMMISSION))/bp; cash=0.0; entry=bp
        elif shares>0 and (bool(sell.iloc[i]) or not bool(regime.iloc[i]) or p<=entry*(1-c["stop_loss"])):
            cash=shares*p*(1-SLIPPAGE)*(1-COMMISSION); shares=0.0; trades+=1
        values.append(cash+shares*p)
    if not values:return None
    ret=(values[-1]-1)*100; peak=values[0]; dd=0.0
    for v in values:
        peak=max(peak,v); dd=max(dd,(peak-v)/peak*100 if peak else 0)
    return {"return":ret,"drawdown":dd,"trades":trades,"score":ret-0.5*dd}

def choose_strategy(training):
    choices=[]
    for c in CANDIDATES:
        r=simple_training_test(training,c)
        if r and r["trades"]>=3 and r["drawdown"]<=30: choices.append((r["score"],c,r))
    if not choices:return None,0.0
    choices.sort(key=lambda x:x[0],reverse=True); score,c,r=choices[0]
    if score<=0 or r["return"]<=0:return None,0.0
    if score<10:a=0.25
    elif score<25:a=0.50
    else:a=0.75
    return c,a

def max_drawdown(curve):
    peak=curve[0]; worst=0.0
    for v in curve:
        peak=max(peak,v); worst=max(worst,(peak-v)/peak*100 if peak else 0)
    return worst

def load_prices():
    frames=[]
    for ticker in TICKERS:
        d=yf.download(ticker,period="10y",interval="1d",auto_adjust=False,progress=False)
        s=d["Close"]
        if hasattr(s,"columns"):s=s.iloc[:,0]
        frames.append(s.rename(ticker))
    return pd.concat(frames,axis=1).dropna()

def run_portfolio(prices):
    cash=STARTING_MONEY; shares={t:0.0 for t in TICKERS}; entry={t:0.0 for t in TICKERS}
    equity_curve=[STARTING_MONEY]; window_returns=[]; trade_count=0; selections=[]; start=0
    while True:
        train_end=start+TRAIN_DAYS; test_end=train_end+TEST_DAYS
        if test_end>len(prices):break
        configs={}; requested={}
        for t in TICKERS:
            c,a=choose_strategy(prices[t].iloc[start:train_end]); configs[t]=c; requested[t]=a
        active=[t for t in TICKERS if configs[t] is not None and requested[t]>0]
        usable=1-MIN_CASH_RESERVE; weights={t:0.0 for t in TICKERS}
        if active:
            raw={t:min(MAX_STOCK_WEIGHT,requested[t]/len(active)) for t in active}; total=sum(raw.values()); scale=min(1.0,usable/total) if total>0 else 0
            for t in active:weights[t]=raw[t]*scale
        window_start_equity=equity_curve[-1]
        for i in range(train_end,test_end):
            portfolio_value=cash+sum(shares[t]*float(prices[t].iloc[i]) for t in TICKERS)
            for t in TICKERS:
                c=configs[t]; p=float(prices[t].iloc[i])
                # If the new walk-forward window selects CASH for a stock, close any
                # position inherited from the previous window before evaluating signals.
                if c is None:
                    if shares[t]>0:
                        cash+=shares[t]*p*(1-SLIPPAGE)*(1-COMMISSION); shares[t]=0.0; entry[t]=0.0; trade_count+=1
                    continue
                hist=prices[t].iloc[max(0,i-REGIME_MA_DAYS+1):i+1]
                regime_ok=len(hist)>=REGIME_MA_DAYS and p>float(hist.mean())
                if c["type"]=="ma":
                    fast=float(prices[t].iloc[i-c["fast"]+1:i+1].mean()); slow=float(prices[t].iloc[i-c["slow"]+1:i+1].mean()); buy=fast>slow; sell=fast<slow
                else:
                    m=p/float(prices[t].iloc[i-c["lookback"]])-1; buy=m>c["threshold"]; sell=m<0
                if shares[t]>0 and (sell or not regime_ok or p<=entry[t]*(1-c["stop_loss"])):
                    cash+=shares[t]*p*(1-SLIPPAGE)*(1-COMMISSION); shares[t]=0.0; entry[t]=0.0; trade_count+=1
                elif shares[t]==0 and buy and regime_ok and weights[t]>0:
                    target=portfolio_value*weights[t]; amount=min(cash,max(0,target))
                    if amount>1:
                        bp=p*(1+SLIPPAGE); shares[t]=(amount*(1-COMMISSION))/bp; cash-=amount; entry[t]=bp
            value=cash+sum(shares[t]*float(prices[t].iloc[i]) for t in TICKERS); equity_curve.append(value)
        end_equity=equity_curve[-1]; window_returns.append((end_equity/window_start_equity-1)*100)
        selections.append({t:(configs[t]["name"] if configs[t] else "CASH",round(weights[t]*100,1)) for t in TICKERS}); start+=TEST_DAYS
    final=equity_curve[-1]; years=(len(window_returns)*TEST_DAYS)/TRADING_DAYS
    returns=[r/100 for r in window_returns]; mean=sum(returns)/len(returns) if returns else 0
    var=sum((x-mean)**2 for x in returns)/(len(returns)-1) if len(returns)>1 else 0; std=math.sqrt(var)
    return {"final":final,"total":(final/STARTING_MONEY-1)*100,"cagr":((final/STARTING_MONEY)**(1/years)-1)*100 if years>0 and final>0 else 0,"mdd":max_drawdown(equity_curve),"vol":std*math.sqrt(TRADING_DAYS/TEST_DAYS)*100,"sharpe":mean/std*math.sqrt(TRADING_DAYS/TEST_DAYS) if std>0 else 0,"trades":trade_count,"windows":len(window_returns),"years":years,"selections":selections}

def equal_weight_hold(prices,test_start,total_days):
    start_prices=prices.iloc[test_start]; end_prices=prices.iloc[min(test_start+total_days-1,len(prices)-1)]
    growth=sum(float(end_prices[t]/start_prices[t]) for t in TICKERS)/len(TICKERS); return STARTING_MONEY*growth

def run_all_tests():
    print("VERSION 6: ONE-ACCOUNT MULTI-STOCK PORTFOLIO")
    print("One simulated $10,000 account is shared across AAPL, MSFT, NVDA, and AMZN.")
    print("Rules: max 30% target weight per stock, at least 10% cash capacity, transaction costs, regime filter, and walk-forward strategy selection.")
    prices=load_prices(); r=run_portfolio(prices); total_days=r["windows"]*TEST_DAYS
    benchmark=equal_weight_hold(prices,TRAIN_DAYS,total_days); benchmark_return=(benchmark/STARTING_MONEY-1)*100
    print("\n========== VERSION 6 PORTFOLIO SCOREBOARD ==========")
    print("Unseen windows:",r["windows"],"| Approx unseen years:",round(r["years"],2))
    print("Starting simulated account: $",round(STARTING_MONEY,2)); print("Bot ending simulated account: $",round(r["final"],2))
    print("Equal-weight Buy & Hold ending value: $",round(benchmark,2)); print("Bot compounded total return:",round(r["total"],2),"%")
    print("Equal-weight Buy & Hold return:",round(benchmark_return,2),"%"); print("Bot estimated CAGR:",round(r["cagr"],2),"%")
    print("Bot max daily portfolio drawdown:",round(r["mdd"],2),"%"); print("Bot annualized window volatility:",round(r["vol"],2),"%")
    print("Bot window-based Sharpe (0% risk-free assumption):",round(r["sharpe"],2)); print("Completed simulated trades:",r["trades"])
    print("\nLast 3 walk-forward allocations:")
    for idx,s in list(enumerate(r["selections"],1))[-3:]:print("Window",idx,":",s)

def main():
    os.makedirs(RESULTS_DIR,exist_ok=True); original=sys.stdout
    with open(RESULTS_FILE,"w",encoding="utf-8") as f:
        sys.stdout=Tee(original,f)
        try:
            print("Trading Bot Automated Research Results"); print("Saved to:",RESULTS_FILE); run_all_tests()
        finally:sys.stdout=original
    print("\nResults saved successfully to:",RESULTS_FILE)

if __name__=="__main__":main()
