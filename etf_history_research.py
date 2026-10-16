"""Historical ETF price comparison for educational research only."""
import csv
import pathlib
import urllib.request
import datetime as dt
import json

ROOT=pathlib.Path(__file__).resolve().parent
OUT=ROOT/"research"/"etf_history.csv"
FUNDS=("VOO","VTI","QQQ","SPY","FXAIX")
def fetch(symbol):
    url=f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5y&interval=1mo"
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; EducationalResearch/1.0)"})
    with urllib.request.urlopen(req,timeout=25) as response:
        data=json.load(response)
    result=data["chart"]["result"][0]
    timestamps=result["timestamp"]
    adj=(result["indicators"].get("adjclose") or [{}])[0].get("adjclose")
    prices=adj if adj else result["indicators"]["quote"][0]["close"]
    return [(dt.datetime.fromtimestamp(ts,dt.timezone.utc).strftime("%Y-%m"),float(price)) for ts,price in zip(timestamps,prices) if price is not None and float(price)>0]
def main():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    data={}
    for fund in FUNDS:
        try:
            data[fund]=dict(fetch(fund))
            print(fund,len(data[fund]),"monthly observations")
        except Exception as e:
            print(fund,"unavailable:",str(e)[:150])
    # Do not invent missing prices; each series is normalized from its own first available point.
    with OUT.open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f);w.writerow(["month","fund","indexed_value","price_basis"])
        for fund,history in data.items():
            if len(history)<12:continue
            base=next(iter(history.values()))
            for month,price in sorted(history.items()):
                w.writerow([month,fund,round(100*price/base,4),"adjusted_close_when_available"])
    if not any(len(v)>=12 for v in data.values()):
        raise RuntimeError("No sufficient ETF data available; investigate source before using comparison.")
if __name__=="__main__":main()
