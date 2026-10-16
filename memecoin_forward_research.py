"""Append-only forward observation of memecoin research signals, no trading."""
import csv, os
from datetime import date
import pandas as pd

SOURCE="crypto_paper/latest_signals.csv"
DEST="crypto_paper/forward_signals.csv"
def main():
    if not os.path.exists(SOURCE): return
    rows=pd.read_csv(SOURCE).fillna("")
    if rows.empty:return
    os.makedirs("crypto_paper",exist_ok=True)
    existing=pd.read_csv(DEST).fillna("") if os.path.exists(DEST) else pd.DataFrame(columns=["observed_date","ticker","signal","close","next_date","next_close","next_return_pct"])
    records=existing.to_dict("records")
    for _,row in rows.iterrows():
        ticker=str(row["ticker"]); d=str(row["date_utc"]); price=pd.to_numeric(row.get("close",""),errors="coerce")
        if pd.notna(price) and price>0:
            for rec in records:
                if rec["ticker"]==ticker and rec["observed_date"]<d and not rec["next_date"]:
                    rec["next_date"]=d;rec["next_close"]=float(price)
                    rec["next_return_pct"]=round((float(price)/float(rec["close"])-1)*100,4)
        if not any(rec["ticker"]==ticker and rec["observed_date"]==d for rec in records):
            records.append({"observed_date":d,"ticker":ticker,"signal":str(row.get("signal","")),"close":float(price) if pd.notna(price) and price>0 else "","next_date":"","next_close":"","next_return_pct":""})
    pd.DataFrame(records,columns=["observed_date","ticker","signal","close","next_date","next_close","next_return_pct"]).to_csv(DEST,index=False)
    print("Forward signal observations:",len(records),"completed:",sum(bool(r["next_date"]) for r in records))
if __name__=="__main__":main()
