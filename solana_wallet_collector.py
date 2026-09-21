"""Read-only public Solana wallet activity collector for research.

No private keys, signing, transaction submission, exchange connection, or real trades.
Both supported watchlist formats are normalized into the same read-only wallet list.
"""
import csv,json,os,time,urllib.request
from datetime import datetime,timezone
RPC_URL=os.environ.get("SOLANA_RPC_URL","https://api.mainnet-beta.solana.com")
WATCHLIST_FILE="smart_money/wallet_watchlist.json";EVENTS_FILE="smart_money/wallet_events.csv";STATE_FILE="smart_money/wallet_collector_state.json"
MAX_SIGNATURES_PER_WALLET=20;MAX_RETRIES=3
def rpc_call(method,params):
 last=None
 for attempt in range(MAX_RETRIES):
  try:
   body=json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params}).encode()
   req=urllib.request.Request(RPC_URL,data=body,headers={"Content-Type":"application/json","User-Agent":"trading-bot-research/1.0"},method="POST")
   with urllib.request.urlopen(req,timeout=20) as r:p=json.loads(r.read().decode())
   if p.get("error"):raise RuntimeError(p["error"])
   return p.get("result")
  except Exception as e:
   last=e
   if attempt<MAX_RETRIES-1:time.sleep(0.5*(2**attempt))
 raise last
def load_json(path,default):
 if not os.path.exists(path):return default
 try:
  with open(path,encoding="utf-8") as f:return json.load(f)
 except Exception:return default
def save_json(path,data):
 os.makedirs(os.path.dirname(path),exist_ok=True)
 with open(path,"w",encoding="utf-8") as f:json.dump(data,f,indent=2,sort_keys=True)
def normalize_wallets(w):
 out=[];seen=set()
 for a in w.get("solana_wallets",[]):
  if isinstance(a,str) and a.strip() and a.strip() not in seen:seen.add(a.strip());out.append(a.strip())
 for item in w.get("wallets",[]):
  if isinstance(item,dict):
   a=str(item.get("address","")).strip()
   if a and a not in seen:seen.add(a);out.append(a)
 return out
def existing_keys():
 if not os.path.exists(EVENTS_FILE):return set()
 with open(EVENTS_FILE,newline="",encoding="utf-8") as f:return {(r.get("signature",""),r.get("mint",""),r.get("direction","")) for r in csv.DictReader(f)}
def balances(meta,owner,side):
 out={}
 for x in meta.get(side,[]) or []:
  if x.get("owner")!=owner:continue
  mint=x.get("mint");amount=(x.get("uiTokenAmount") or {}).get("uiAmount")
  if mint and amount is not None:out[mint]=out.get(mint,0)+float(amount)
 return out
def events(wallet,sig,tx):
 if not tx or not tx.get("meta"):return []
 meta=tx["meta"];pre=balances(meta,wallet,"preTokenBalances");post=balances(meta,wallet,"postTokenBalances");bt=tx.get("blockTime")
 et=datetime.fromtimestamp(bt,tz=timezone.utc).isoformat() if bt else ""
 now=datetime.now(timezone.utc).isoformat();out=[]
 for mint in sorted(set(pre)|set(post)):
  delta=post.get(mint,0)-pre.get(mint,0)
  if abs(delta)<1e-12:continue
  out.append({"observed_at_utc":now,"event_time_utc":et,"wallet":wallet,"signature":sig,"mint":mint,"direction":"ACQUIRE" if delta>0 else "DISPOSE","token_delta":delta})
 return out
def append(rows):
 if not rows:return
 fields=["observed_at_utc","event_time_utc","wallet","signature","mint","direction","token_delta"];exists=os.path.exists(EVENTS_FILE)
 with open(EVENTS_FILE,"a",newline="",encoding="utf-8") as f:
  w=csv.DictWriter(f,fieldnames=fields)
  if not exists:w.writeheader()
  w.writerows(rows)
def main():
 os.makedirs("smart_money",exist_ok=True);watch=load_json(WATCHLIST_FILE,{"solana_wallets":[]});wallets=normalize_wallets(watch);known=existing_keys();new=[];errors=[];successful=0
 for wallet in wallets:
  try:
   sigs=rpc_call("getSignaturesForAddress",[wallet,{"limit":MAX_SIGNATURES_PER_WALLET}]) or []
   for item in reversed(sigs):
    sig=item.get("signature")
    if not sig:continue
    tx=rpc_call("getTransaction",[sig,{"encoding":"jsonParsed","maxSupportedTransactionVersion":0}])
    for e in events(wallet,sig,tx):
     key=(e["signature"],e["mint"],e["direction"])
     if key not in known:known.add(key);new.append(e)
    time.sleep(.08)
   successful+=1
  except Exception as e:errors.append({"wallet":wallet,"error":str(e)[:300]})
 append(new);state={"last_run_utc":datetime.now(timezone.utc).isoformat(),"wallets_checked":len(wallets),"wallets_successful":successful,"wallets_failed":len(errors),"new_events":len(new),"errors":errors}
 save_json(STATE_FILE,state)
 print("READ-ONLY SOLANA WALLET RESEARCH COLLECTOR");print("Wallets checked:",len(wallets));print("Successful:",successful,"Failed:",len(errors));print("New token balance-change events:",len(new))
 if not wallets:print("Watchlist is empty; no wallet addresses were invented or added.")
 print("No transactions were signed or submitted.")
if __name__=="__main__":main()
