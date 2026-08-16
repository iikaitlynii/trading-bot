import os
import sys
import math
import pandas as pd
import yfinance as yf

TICKERS=["AAPL","MSFT","NVDA","AMZN"]
STARTING_MONEY=10000
COMMISSION=0.001
SLIPPAGE=0.001
TRAIN_DAYS=500
TEST_DAYS=125
REGIME_MA_DAYS=200
TRADING_DAYS=252
MAX_STOCK_WEIGHT=0.30
MIN_CASH_RESERVE=0.15
MOMENTUM_LOOKBACK=126
VOL_LOOKBACK=63
TARGET_STOCK_VOL=0.25
RESULTS_DIR="results"
RESULTS_FILE=os.path.join(RESULTS_DIR,"latest_results.txt")

CANDIDATES=[
 {"name":"MA 5/20","type":"ma","fast":5,"slow":20,"stop_loss":0.02},
 {"name":"MA 10/30","type":"ma","fast":10,"slow":30,"stop_loss":0.03},
 {"name":"MA 20/50","type":"ma","fast":20,"slow":50,"stop_loss":0.04},
 {"name":"Momentum 10d 3%","type":"momentum","lookback":10,"threshold":0.03,"stop_loss":0.02},
 {"name":"Momentum 20d 5%","type":"momentum","lookback":20,"threshold":0.05,"stop_loss":0.03},
 {"name":"Momentum 30d 7%","type":"momentum","lookback":30,"threshold":0.07,"stop_loss":0.04},
]

class Tee:
 def __init__(self,*streams):self.streams=streams
 def write(self,text):
  for s in self.streams:s.write(text);s.flush()
 def flush(self):
  for s in self.streams:s.flush()

def candidate_signals(prices,c):
 if c["type"]=="ma":
  fast=prices.rolling(c["fast"]).mean();slow=prices.rolling(c["slow"]).mean();return fast>slow,fast<slow
 mom=prices.pct_change(c["lookback"]);return mom>c["threshold"],mom<0

def simple_training_test(prices,c):
 buy,sell=candidate_signals(prices,c);regime=prices>prices.rolling(REGIME_MA_DAYS).mean();cash=1.;shares=0.;entry=0.;values=[];trades=0
 for i in range(REGIME_MA_DAYS,len(prices)):
  p=float(prices.iloc[i])
  if shares==0 and bool(buy.iloc[i]) and bool(regime.iloc[i]):
   bp=p*(1+SLIPPAGE);shares=(cash*(1-COMMISSION))/bp;cash=0.;entry=bp
  elif shares>0 and (bool(sell.iloc[i]) or not bool(regime.iloc[i]) or p<=entry*(1-c["stop_loss"])):
   cash=shares*p*(1-SLIPPAGE)*(1-COMMISSION);shares=0.;trades+=1
  values.append(cash+shares*p)
 if not values:return None
 ret=(values[-1]-1)*100;peak=values[0];dd=0.
 for v in values:peak=max(peak,v);dd=max(dd,(peak-v)/peak*100 if peak else 0)
 return {"return":ret,"drawdown":dd,"trades":trades,"score":ret-.5*dd}

def choose_strategy(training):
 choices=[]
 for c in CANDIDATES:
  r=simple_training_test(training,c)
  if r and r["trades"]>=3 and r["drawdown"]<=30:choices.append((r["score"],c,r))
 if not choices:return None,0.
 choices.sort(key=lambda x:x[0],reverse=True);score,c,r=choices[0]
 if score<=0 or r["return"]<=0:return None,0.
 return c,min(.75,max(.25,score/35))

def max_drawdown(curve):
 peak=curve[0];worst=0.
 for v in curve:peak=max(peak,v);worst=max(worst,(peak-v)/peak*100 if peak else 0)
 return worst

def load_prices():
 frames=[]
 for t in TICKERS:
  d=yf.download(t,period="10y",interval="1d",auto_adjust=False,progress=False);s=d["Close"]
  if hasattr(s,"columns"):s=s.iloc[:,0]
  frames.append(s.rename(t))
 return pd.concat(frames,axis=1).dropna()

def risk_adjusted_weights(prices,train_end,configs,requested):
 scores={}
 for t in TICKERS:
  if configs[t] is None or requested[t]<=0:continue
  s=prices[t].iloc[:train_end]
  if len(s)<max(MOMENTUM_LOOKBACK,REGIME_MA_DAYS,VOL_LOOKBACK)+1:continue
  momentum=float(s.iloc[-1]/s.iloc[-MOMENTUM_LOOKBACK]-1)
  ma=float(s.iloc[-REGIME_MA_DAYS:].mean());trend=max(0.,float(s.iloc[-1]/ma-1)) if ma>0 else 0.
  returns=s.pct_change().dropna().iloc[-VOL_LOOKBACK:];daily_vol=float(returns.std())
  annual_vol=daily_vol*math.sqrt(TRADING_DAYS)
  strength=max(0.,momentum)+trend
  if strength<=0 or annual_vol<=0:continue
  vol_scale=min(1.,TARGET_STOCK_VOL/annual_vol)
  scores[t]=strength*vol_scale
 weights={t:0. for t in TICKERS}
 if not scores:return weights
 usable=1-MIN_CASH_RESERVE;total=sum(scores.values())
 for t,score in scores.items():weights[t]=min(MAX_STOCK_WEIGHT,usable*score/total)
 remaining=usable-sum(weights.values())
 # Only redistribute while respecting both concentration and volatility limits.
 for t in sorted(scores,key=scores.get,reverse=True):
  if remaining<=1e-9:break
  s=prices[t].iloc[:train_end];annual_vol=float(s.pct_change().dropna().iloc[-VOL_LOOKBACK:].std())*math.sqrt(TRADING_DAYS)
  risk_cap=min(MAX_STOCK_WEIGHT,MAX_STOCK_WEIGHT*min(1.,TARGET_STOCK_VOL/annual_vol)) if annual_vol>0 else 0.
  add=min(max(0.,risk_cap-weights[t]),remaining);weights[t]+=add;remaining-=add
 return weights

def run_portfolio(prices):
 cash=STARTING_MONEY;shares={t:0. for t in TICKERS};entry={t:0. for t in TICKERS};equity=[STARTING_MONEY];window_returns=[];trade_count=0;selections=[];start=0
 while True:
  train_end=start+TRAIN_DAYS;test_end=train_end+TEST_DAYS
  if test_end>len(prices):break
  configs={};requested={}
  for t in TICKERS:configs[t],requested[t]=choose_strategy(prices[t].iloc[start:train_end])
  weights=risk_adjusted_weights(prices,train_end,configs,requested);window_start=equity[-1]
  for i in range(train_end,test_end):
   portfolio_value=cash+sum(shares[t]*float(prices[t].iloc[i]) for t in TICKERS)
   for t in TICKERS:
    c=configs[t];p=float(prices[t].iloc[i])
    if c is None or weights[t]<=0:
     if shares[t]>0:cash+=shares[t]*p*(1-SLIPPAGE)*(1-COMMISSION);shares[t]=0.;entry[t]=0.;trade_count+=1
     continue
    hist=prices[t].iloc[i-REGIME_MA_DAYS+1:i+1];regime_ok=len(hist)>=REGIME_MA_DAYS and p>float(hist.mean())
    if c["type"]=="ma":
     fast=float(prices[t].iloc[i-c["fast"]+1:i+1].mean());slow=float(prices[t].iloc[i-c["slow"]+1:i+1].mean());buy=fast>slow;sell=fast<slow
    else:
     m=p/float(prices[t].iloc[i-c["lookback"]])-1;buy=m>c["threshold"];sell=m<0
    if shares[t]>0 and (sell or not regime_ok or p<=entry[t]*(1-c["stop_loss"])):
     cash+=shares[t]*p*(1-SLIPPAGE)*(1-COMMISSION);shares[t]=0.;entry[t]=0.;trade_count+=1
    elif shares[t]==0 and buy and regime_ok:
     target=portfolio_value*weights[t];amount=min(cash,max(0.,target))
     if amount>1:
      bp=p*(1+SLIPPAGE);shares[t]=(amount*(1-COMMISSION))/bp;cash-=amount;entry[t]=bp
   equity.append(cash+sum(shares[t]*float(prices[t].iloc[i]) for t in TICKERS))
  window_returns.append((equity[-1]/window_start-1)*100);selections.append({t:(configs[t]["name"] if configs[t] else "CASH",round(weights[t]*100,1)) for t in TICKERS});start+=TEST_DAYS
 final=equity[-1];years=len(window_returns)*TEST_DAYS/TRADING_DAYS;rs=[x/100 for x in window_returns];mean=sum(rs)/len(rs) if rs else 0.;var=sum((x-mean)**2 for x in rs)/(len(rs)-1) if len(rs)>1 else 0.;std=math.sqrt(var)
 return {"final":final,"total":(final/STARTING_MONEY-1)*100,"cagr":((final/STARTING_MONEY)**(1/years)-1)*100 if years and final>0 else 0.,"mdd":max_drawdown(equity),"vol":std*math.sqrt(TRADING_DAYS/TEST_DAYS)*100,"sharpe":mean/std*math.sqrt(TRADING_DAYS/TEST_DAYS) if std else 0.,"trades":trade_count,"windows":len(window_returns),"years":years,"selections":selections}

def equal_weight_hold(prices,test_start,total_days):
 a=prices.iloc[test_start];b=prices.iloc[min(test_start+total_days-1,len(prices)-1)];return STARTING_MONEY*sum(float(b[t]/a[t]) for t in TICKERS)/len(TICKERS)

def run_all_tests():
 print("VERSION 8: VOLATILITY-ADJUSTED RELATIVE-STRENGTH ALLOCATION")
 print("One simulated $10,000 account. Strong trends still receive preference, but higher-volatility stocks receive smaller target weights.")
 print("Risk limits: max 30% per stock, at least 15% cash capacity, 63-day volatility estimate, 25% annualized stock-vol target, transaction costs, stop losses, and 200-day regime filter.")
 prices=load_prices();r=run_portfolio(prices);days=r["windows"]*TEST_DAYS;bench=equal_weight_hold(prices,TRAIN_DAYS,days);br=(bench/STARTING_MONEY-1)*100
 print("\n========== VERSION 8 PORTFOLIO SCOREBOARD ==========")
 print("Unseen windows:",r["windows"],"| Approx unseen years:",round(r["years"],2));print("Starting simulated account: $",STARTING_MONEY);print("Bot ending simulated account: $",round(r["final"],2));print("Equal-weight Buy & Hold ending value: $",round(bench,2));print("Bot compounded total return:",round(r["total"],2),"%");print("Equal-weight Buy & Hold return:",round(br,2),"%");print("Bot estimated CAGR:",round(r["cagr"],2),"%");print("Bot max daily portfolio drawdown:",round(r["mdd"],2),"%");print("Bot annualized window volatility:",round(r["vol"],2),"%");print("Bot window-based Sharpe (0% risk-free assumption):",round(r["sharpe"],2));print("Completed simulated trades:",r["trades"])
 print("\nLast 3 walk-forward allocations:")
 for idx,s in list(enumerate(r["selections"],1))[-3:]:print("Window",idx,":",s)

def main():
 os.makedirs(RESULTS_DIR,exist_ok=True);original=sys.stdout
 with open(RESULTS_FILE,"w",encoding="utf-8") as f:
  sys.stdout=Tee(original,f)
  try:print("Trading Bot Automated Research Results");print("Saved to:",RESULTS_FILE);run_all_tests()
  finally:sys.stdout=original
 print("\nResults saved successfully to:",RESULTS_FILE)

if __name__=="__main__":main()
