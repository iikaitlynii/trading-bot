"""Health/evidence report for the read-only smart-money research pipeline."""
import csv,json,os
from collections import Counter
D="smart_money"
def rows(name):
 p=os.path.join(D,name)
 if not os.path.exists(p):return []
 with open(p,newline="",encoding="utf-8") as f:return list(csv.DictReader(f))
def main():
 os.makedirs(D,exist_ok=True);events=rows("wallet_events.csv");obs=rows("observations.csv");outcomes=rows("outcomes.csv");candidates=rows("candidate_scores.csv")
 horizons=Counter(r.get("horizon_hours","") for r in outcomes);statuses=Counter(r.get("status","") for r in candidates);state={}
 p=os.path.join(D,"wallet_collector_state.json")
 if os.path.exists(p):
  try:
   with open(p,encoding="utf-8") as f:state=json.load(f)
  except Exception:pass
 issues=[]
 if not events:issues.append("No public wallet events collected yet.")
 if events and not obs:issues.append("Wallet events exist but no observations passed market/liquidity checks.")
 if obs and not outcomes:issues.append("Observations exist but no forward horizons are due/recorded yet.")
 if state.get("errors"):issues.append("Collector reported %d error(s)."%len(state["errors"]))
 report=["SMART-MONEY RESEARCH HEALTH REPORT","Read-only research only — no transactions or wallet control.","",
 "Wallets checked: %s"%state.get("wallets_checked",0),"Public wallet events: %d"%len(events),"Research observations: %d"%len(obs),
 "Forward outcomes: %d"%len(outcomes),"1h / 24h / 7d outcomes: %d / %d / %d"%(horizons["1"],horizons["24"],horizons["168"]),
 "Candidate records: %d"%len(candidates),"Research-candidate labels: %d"%statuses["RESEARCH_CANDIDATE"],"More-data-needed labels: %d"%statuses["MORE_DATA_NEEDED"],"","DATA QUALITY"]
 report += ["- "+x for x in issues] if issues else ["No structural data-quality warnings detected."]
 report += ["","READINESS"]
 if horizons["24"]<30:report.append("EARLY: fewer than 30 recorded 24h outcomes. Keep collecting forward evidence.")
 elif horizons["24"]<100:report.append("DEVELOPING: useful evidence is accumulating; continue across more market conditions.")
 else:report.append("MATURE SAMPLE: 100+ recorded 24h outcomes exist, but historical results still do not predict profits.")
 text="\n".join(report)+"\n"
 with open(os.path.join(D,"health_report.txt"),"w",encoding="utf-8") as f:f.write(text)
 print(text)
if __name__=="__main__":main()
