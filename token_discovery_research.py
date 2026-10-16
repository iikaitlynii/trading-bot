"""Read-only public token-profile research snapshot. Never places orders."""
import csv
import datetime as dt
import json
import pathlib
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "crypto_paper" / "discovered_tokens.csv"
HEADERS = ["observed_utc","chain","symbol","name","token_address","pair_age_hours","liquidity_usd","volume_24h_usd","price_change_24h_pct","market_cap_usd","research_flags","source"]
BASE = "https://api.dexscreener.com"
def get(path):
    req=urllib.request.Request(BASE+path,headers={"User-Agent":"PaperResearchDashboard/1.0","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=20) as resp:
        return json.load(resp)
def num(v):
    try: return float(v)
    except (TypeError,ValueError): return None
def main():
    profiles=get("/token-profiles/latest/v1")
    addresses=list(dict.fromkeys(p.get("tokenAddress") for p in profiles if p.get("chainId")=="solana" and p.get("tokenAddress")))[:30]
    pairs=get("/tokens/v1/solana/"+",".join(addresses)) if addresses else []
    best={}
    for p in pairs if isinstance(pairs,list) else []:
        addr=(p.get("baseToken") or {}).get("address")
        if addr in addresses and (addr not in best or (num((p.get("liquidity") or {}).get("usd")) or 0)>(num((best[addr].get("liquidity") or {}).get("usd")) or 0)):best[addr]=p
    now=dt.datetime.now(dt.timezone.utc)
    rows=[]
    for addr in addresses:
        p=best.get(addr,{})
        if not p:continue
        created=num(p.get("pairCreatedAt"))
        age=(now.timestamp()*1000-created)/3600000 if created else None
        liquidity=num((p.get("liquidity") or {}).get("usd"))
        volume=num((p.get("volume") or {}).get("h24"))
        change=num((p.get("priceChange") or {}).get("h24"))
        flags=[]
        if age is None:flags.append("AGE_UNKNOWN")
        elif age<24:flags.append("NEW_PAIR")
        if liquidity is None:flags.append("LIQUIDITY_UNKNOWN")
        elif liquidity<50000:flags.append("LOW_LIQUIDITY")
        if volume is None:flags.append("VOLUME_UNKNOWN")
        if change is not None and abs(change)>50:flags.append("LARGE_PRICE_SWING")
        flags.append("CONTRACT_AND_HOLDERS_UNVERIFIED")
        token=p.get("baseToken") or {}
        rows.append([now.isoformat(timespec="seconds"),"solana",token.get("symbol",""),token.get("name",""),addr,round(age,1) if age is not None else "",liquidity if liquidity is not None else "",volume if volume is not None else "",change if change is not None else "",num(p.get("marketCap")) or "", "|".join(flags),"DEX Screener latest token profiles"])
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f);w.writerow(HEADERS);w.writerows(rows)
    print(f"Saved {len(rows)} observed token profiles; no trading decisions.")
if __name__=="__main__":main()
