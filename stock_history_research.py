"""Read-only stock daily history snapshots for charting and walk-forward research.
No brokerage connections or orders. Yahoo public endpoint may be unavailable.
"""
import csv,datetime as dt,json,pathlib,urllib.request,time
ROOT=pathlib.Path(__file__).resolve().parent
OUT=ROOT/"research"/"stock_history.csv"
SYMBOLS=("AAPL","MSFT","NVDA","AMZN")
def fetch(symbol):
    url=f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=2y&interval=1d"
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (EducationalResearch/1.0)","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=30) as response:data=json.load(response)
    result=data["chart"]["result"][0];q=result["indicators"]["quote"][0]
    rows=[]
    for i,ts in enumerate(result["timestamp"]):
        close=q["close"][i];high=q["high"][i];low=q["low"][i]
        if any(v is None for v in (close,high,low)):continue
        rows.append((dt.datetime.fromtimestamp(ts,dt.timezone.utc).strftime("%Y-%m-%d"),symbol,round(float(close),5),round(float(high),5),round(float(low),5),int(q["volume"][i] or 0)))
    return rows
def main():
    collected=[]
    for symbol in SYMBOLS:
        try:
            rows=fetch(symbol)
            if len(rows)<150:raise ValueError("insufficient sessions")
            collected.extend(rows);print(symbol,len(rows),"daily observations")
        except Exception as exc:print(symbol,"unavailable",str(exc)[:120])
        time.sleep(.5)
    if not collected:raise RuntimeError("No stock history collected; preserving previous snapshot")
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f);w.writerow(("date","ticker","close","high","low","volume"));w.writerows(collected)
if __name__=="__main__":main()
