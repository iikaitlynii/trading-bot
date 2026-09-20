"""Build forward-valid research observations from public Solana wallet events.

Read-only research bridge. Entry price and observation time are captured together
at builder runtime so older wallet-event timestamps cannot create look-ahead bias.
"""
import csv,json,os,urllib.parse,urllib.request
from datetime import datetime,timezone
EVENTS_FILE="smart_money/wallet_events.csv";OBS_FILE="smart_money/observations.csv";WATCHLIST_FILE="smart_money/wallet_watchlist.json"
DEX_URL="https://api.dexscreener.com/latest/dex/tokens/{}";MIN_LIQUIDITY_USD=10000.0
FIELDS=["observation_id","observed_at_utc","source_event_time_utc","source_label","wallet_label","wallet_address","token","contract","mint","network","entry_price_usd","source_count","wallet_quality","wallet_consensus","social_confirmation","liquidity_quality","momentum_confirmation","risk_quality"]
def load_csv(path):
 if not os.path.exists(path):return []
 with open(path,newline="",encoding="utf-8") as f:return list(csv.DictReader(f))
def wallet_labels():
 if not os.path.exists(WATCHLIST_FILE):return {}
 try:
  with open(WATCHLIST_FILE,encoding="utf-8") as f:data=json.load(f)
 except Exception:return {}
 labels={}
 for a in data.get("solana_wallets",[]):
  if isinstance(a,str) and a.strip():labels[a.strip()]=a.strip()[:8]
 for item in data.get("wallets",[]):
  if isinstance(item,dict) and item.get("address"):labels[item["address"]]=item.get("label") or item["address"][:8]
 return labels
def fetch_market(mint):
 req=urllib.request.Request(DEX_URL.format(urllib.parse.quote(mint,safe="")),headers={"User-Agent":"trading-bot-research/1.0"})
 with urllib.request.urlopen(req,timeout=20) as resp:payload=json.loads(resp.read().decode())
 usable=[]
 for pair in payload.get("pairs") or []:
  try:price=float(pair.get("priceUsd"));liq=float((pair.get("liquidity") or {}).get("usd") or 0)
  except (TypeError,ValueError):continue
  if price>0:usable.append((liq,price,pair))
 if not usable:return None
 liq,price,pair=max(usable,key=lambda x:x[0])
 return {"price":price,"liquidity":liq,"symbol":((pair.get("baseToken") or {}).get("symbol") or "UNKNOWN")}
def lscore(x):
 return 90 if x>=1_000_000 else 75 if x>=250_000 else 60 if x>=50_000 else 45 if x>=MIN_LIQUIDITY_USD else 20
def main():
 os.makedirs("smart_money",exist_ok=True);events=load_csv(EVENTS_FILE);existing=load_csv(OBS_FILE);seen={r.get("observation_id","") for r in existing};labels=wallet_labels();new=[];skipped=0
 for event in events:
  if event.get("direction")!="ACQUIRE":continue
  mint=(event.get("mint") or "").strip();wallet=(event.get("wallet") or "").strip();sig=(event.get("signature") or "").strip()
  if not mint or not wallet or not sig:skipped+=1;continue
  oid="|".join([sig,wallet,mint])
  if oid in seen:continue
  try:market=fetch_market(mint)
  except Exception as exc:print("Public market read failed:",mint,str(exc));market=None
  if not market or market["liquidity"]<MIN_LIQUIDITY_USD:skipped+=1;continue
  # This timestamp is intentionally captured with the current market price.
  captured_at=datetime.now(timezone.utc).isoformat()
  source_time=event.get("event_time_utc") or event.get("observed_at_utc") or ""
  q=lscore(market["liquidity"]);label=labels.get(wallet,wallet[:8])
  new.append({"observation_id":oid,"observed_at_utc":captured_at,"source_event_time_utc":source_time,"source_label":label,"wallet_label":label,"wallet_address":wallet,"token":market["symbol"],"contract":mint,"mint":mint,"network":"solana","entry_price_usd":market["price"],"source_count":1,"wallet_quality":50,"wallet_consensus":50,"social_confirmation":50,"liquidity_quality":q,"momentum_confirmation":50,"risk_quality":50 if q>=40 else 20});seen.add(oid)
 if new:
  combined=[{field:r.get(field,"") for field in FIELDS} for r in existing]+new
  with open(OBS_FILE,"w",newline="",encoding="utf-8") as f:w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(combined)
 print("PUBLIC WALLET EVENT -> FORWARD RESEARCH BRIDGE");print("Events read:",len(events));print("New forward-valid observations:",len(new));print("Skipped:",skipped);print("Source event time is provenance only; forward horizons begin at price-capture time.")
if __name__=="__main__":main()
