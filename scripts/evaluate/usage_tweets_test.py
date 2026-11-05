"""Test of the mined forms on real tweets: one tweet per added form, judged by Claude before the detector ran.

  .venv/Scripts/python scripts/evaluate/usage_tweets_test.py <out.json>
Cases and judgements are in git-ignored logs/usage_test_cases.json and logs/usage_test_result.json (tweets stay local).
"""
import json,sys,re,glob
sys.path.insert(0,"src"); sys.path.insert(0,"scripts/enrich")
sys.stdout.reconfigure(encoding="utf-8")
from kass_layer.detector.engine import Detector, normalize
from usage_filter import flat
Y=set(json.load(open("logs/usage_test_result.json",encoding="utf-8"))["labels_true"])
cases=json.load(open("logs/usage_test_cases.json",encoding="utf-8"))
pref={"ai":"4cd164a7","media":"928f4f87","sports":"ae041c6d","finance":"4264f8ae","energy":"f990c2a0","stats":"ee392446","legal":"0f465c61","contracts":"89af196b"}
d=Detector("demo_local")
names=[n.strip() for n in json.load(open("demo_local/index.json",encoding="utf-8"))["dictionaries"]]
dname={p:json.load(open(glob.glob(f"data/dictionaries/enriched/{p}*.enriched.json")[0],encoding="utf-8"))["dictionary_name"].strip() for p in pref.values()}
dom={l:next((dm["id"] for dm in d.domains if names.index(dname[p]) in dm["dicts"]),None) for l,p in pref.items()}
key=lambda t:" ".join(w[2:] if w.startswith("ال") and len(w)>3 else w for w in normalize(re.sub(r"\([^)]*\)"," ",t)).split())
res={"tp":0,"fn":0,"fp":0,"tn":0}; out=[]
for i,c in enumerate(cases,1):
    hit=any(it["state"]!="std" and (flat(c["form"]) in flat(it["original"]) or flat(it["original"]) in flat(c["form"])) and key(d.senses[it["best"][0]][0])==key(c["term"]) for it in d.analyse(c["text"],dom[c["label"]])["items"])
    y=i in Y; k=("tp" if hit else "fn") if y else ("fp" if hit else "tn"); res[k]+=1; out.append(k)
print(res,"recall %.1f%%"%(100*res["tp"]/(res["tp"]+res["fn"])),"false alarms %.1f%%"%(100*res["fp"]/(res["fp"]+res["tn"])),"precision %.1f%%"%(100*res["tp"]/max(1,res["tp"]+res["fp"])))
json.dump(out,open(sys.argv[1],"w"))
