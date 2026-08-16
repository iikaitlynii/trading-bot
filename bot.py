import os
import sys
import yfinance as yf

TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN"]
STARTING_MONEY = 10000
COMMISSION = 0.001
SLIPPAGE = 0.001
TRAIN_DAYS = 500
TEST_DAYS = 125
WARMUP_DAYS = 220
REGIME_MA_DAYS = 200
RESULTS_DIR = "results"
RESULTS_FILE = os.path.join(RESULTS_DIR, "latest_results.txt")
MIN_TRAINING_TRADES = 3
MAX_TRAINING_DRAWDOWN = 30.0

CANDIDATES = [
    {"name": "MA 5/20", "type": "ma", "fast": 5, "slow": 20, "stop_loss": 0.02},
    {"name": "MA 10/30", "type": "ma", "fast": 10, "slow": 30, "stop_loss": 0.03},
    {"name": "MA 20/50", "type": "ma", "fast": 20, "slow": 50, "stop_loss": 0.04},
    {"name": "Momentum 10d 3%", "type": "momentum", "lookback": 10, "threshold": 0.03, "stop_loss": 0.02},
    {"name": "Momentum 20d 5%", "type": "momentum", "lookback": 20, "threshold": 0.05, "stop_loss": 0.03},
    {"name": "Momentum 30d 7%", "type": "momentum", "lookback": 30, "threshold": 0.07, "stop_loss": 0.04},
]

class Tee:
    def __init__(self, *streams): self.streams = streams
    def write(self, text):
        for stream in self.streams:
            stream.write(text); stream.flush()
    def flush(self):
        for stream in self.streams: stream.flush()

def empty_result():
    return {"return":0.0,"drawdown":0.0,"trades":0,"win_rate":0.0,"profit_factor":0.0}

def run_strategy(prices, config, score_start=0, allocation=1.0, use_regime_filter=False):
    prices=prices.dropna()
    if len(prices)<60:return None
    allocation=max(0.0,min(1.0,allocation)); cash=STARTING_MONEY; shares=0.0; entry_price=0.0; in_position=False
    trades=[]; values=[]
    regime_ma=prices.rolling(REGIME_MA_DAYS).mean()
    if config["type"]=="ma":
        fast=prices.rolling(config["fast"]).mean(); slow=prices.rolling(config["slow"]).mean(); first=max(config["slow"],score_start)
    else:
        momentum=prices.pct_change(config["lookback"]); first=max(config["lookback"],score_start)
    for i in range(first,len(prices)):
        price=float(prices.iloc[i])
        if config["type"]=="ma":
            buy=float(fast.iloc[i])>float(slow.iloc[i]); sell=float(fast.iloc[i])<float(slow.iloc[i])
        else:
            m=float(momentum.iloc[i]); buy=m>config["threshold"]; sell=m<0
        regime_ok=True
        if use_regime_filter:
            ma_value=regime_ma.iloc[i]
            regime_ok=(not ma_value != ma_value) and price>float(ma_value)
        if buy and regime_ok and not in_position and allocation>0:
            buy_price=price*(1+SLIPPAGE); amount=cash*allocation; reserved=cash-amount
            shares=(amount*(1-COMMISSION))/buy_price; cash=reserved; entry_price=buy_price; in_position=True
        elif in_position and (price<=entry_price*(1-config["stop_loss"]) or sell or (use_regime_filter and not regime_ok)):
            sell_price=price*(1-SLIPPAGE); trades.append(((sell_price-entry_price)/entry_price)*100)
            cash+=shares*sell_price*(1-COMMISSION); shares=0.0; entry_price=0.0; in_position=False
        values.append(cash+shares*price if in_position else cash)
    if not values:return None
    ret=((values[-1]-STARTING_MONEY)/STARTING_MONEY)*100; peak=values[0]; dd=0.0
    for value in values:
        peak=max(peak,value)
        if peak>0:dd=max(dd,((peak-value)/peak)*100)
    wins=[t for t in trades if t>0]; losses=[t for t in trades if t<0]; tw=sum(wins); tl=abs(sum(losses))
    pf=tw/tl if tl>0 else (float("inf") if tw>0 else 0.0)
    return {"return":ret,"drawdown":dd,"trades":len(trades),"win_rate":len(wins)/len(trades)*100 if trades else 0.0,"profit_factor":pf}

def training_score(r):
    return float("-inf") if r is None else r["return"]-0.5*r["drawdown"]

def choose_best_strategy(training):
    ranked=[]
    for c in CANDIDATES:
        r=run_strategy(training,c)
        if r and r["trades"]>=MIN_TRAINING_TRADES and r["drawdown"]<=MAX_TRAINING_DRAWDOWN:ranked.append((training_score(r),c,r))
    if not ranked:return None,None,0.0,0.0
    ranked.sort(key=lambda x:x[0],reverse=True); score,c,r=ranked[0]
    if score<=0 or r["return"]<=0:a=0.0
    elif score<10:a=0.25
    elif score<25:a=0.50
    else:a=0.75
    return c,r,score,a

def walk_forward(close):
    out=[]; start=0
    while True:
        train_end=start+TRAIN_DAYS; test_start=train_end; test_end=test_start+TEST_DAYS
        if test_end>len(close):break
        c,tr,score,a=choose_best_strategy(close.iloc[start:train_end])
        first=float(close.iloc[test_start]); last=float(close.iloc[test_end-1]); hold=((last-first)/first)*100
        if c is None or a==0:r=empty_result(); name="CASH"
        else:
            warm=max(0,test_start-WARMUP_DAYS); r=run_strategy(close.iloc[warm:test_end],c,test_start-warm,a,True); name=c["name"]
        regime_start=max(0,test_start-REGIME_MA_DAYS+1); history=close.iloc[regime_start:test_start+1]
        regime_ma=float(history.mean()) if len(history)>=REGIME_MA_DAYS else float("nan")
        regime="BULL" if regime_ma==regime_ma and first>regime_ma else "DEFENSIVE"
        out.append({"period":len(out)+1,"strategy":name,"allocation":a,"regime":regime,"training_return":tr["return"] if tr else 0.0,"score":score,"test_return":r["return"],"drawdown":r["drawdown"],"trades":r["trades"],"hold":hold})
        start+=TEST_DAYS
    return out

def summarize(rs):
    n=len(rs)
    if not n:return None
    return {"n":n,"ret":sum(r["test_return"] for r in rs)/n,"hold":sum(r["hold"] for r in rs)/n,"dd":sum(r["drawdown"] for r in rs)/n,"positive":sum(r["test_return"]>0 for r in rs)/n*100,"beat":sum(r["test_return"]>r["hold"] for r in rs)/n*100,"allocation":sum(r["allocation"] for r in rs)/n*100,"cash":sum(r["allocation"]==0 for r in rs)/n*100}

def run_all_tests():
    print("VERSION 4: MARKET REGIME FILTER")
    print("New long entries require price above its trailing 200-day moving average; positions exit if regime turns defensive.")
    print("All regime decisions use only data available at that historical point.")
    for ticker in TICKERS:
        print("\n======================================\nREGIME-FILTERED WALK-FORWARD:",ticker,"\n======================================")
        data=yf.download(ticker,period="10y",interval="1d",auto_adjust=False,progress=False); close=data["Close"]
        if hasattr(close,"columns"):close=close.iloc[:,0]
        close=close.dropna(); rs=walk_forward(close)
        for r in rs:
            print("\nTEST PERIOD:",r["period"],"| Starting regime:",r["regime"])
            print("Chosen:",r["strategy"],"| Simulated allocation:",round(r["allocation"]*100),"%")
            print("Training return:",round(r["training_return"],2),"% | score:",round(r["score"],2))
            print("UNSEEN return:",round(r["test_return"],2),"% | Buy & Hold:",round(r["hold"],2),"%")
            print("UNSEEN drawdown:",round(r["drawdown"],2),"% | trades:",r["trades"])
        s=summarize(rs)
        if s:
            print("\n========== VERSION 4 SUMMARY ==========")
            print("Test periods:",s["n"]); print("Average unseen return:",round(s["ret"],2),"%")
            print("Average Buy & Hold return:",round(s["hold"],2),"%")
            print("Average unseen drawdown:",round(s["dd"],2),"%")
            print("Positive unseen periods:",round(s["positive"],2),"%")
            print("Beat Buy & Hold:",round(s["beat"],2),"%")
            print("Average simulated allocation:",round(s["allocation"],2),"%")
            print("Cash periods:",round(s["cash"],2),"%")

def main():
    os.makedirs(RESULTS_DIR,exist_ok=True); original=sys.stdout
    with open(RESULTS_FILE,"w",encoding="utf-8") as f:
        sys.stdout=Tee(original,f)
        try:
            print("Trading Bot Automated Research Results"); print("Saved to:",RESULTS_FILE); run_all_tests()
        finally:sys.stdout=original
    print("\nResults saved successfully to:",RESULTS_FILE)

if __name__=="__main__":main()
