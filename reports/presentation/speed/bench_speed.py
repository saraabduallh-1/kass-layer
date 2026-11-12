"""Measures replacement (analyse) and unification speed by text length; median of 15 runs, same code as the API.

  .venv/Scripts/python reports/presentation/speed/bench_speed.py reports/presentation/speed/bench.json
"""
from pathlib import Path
import sys, time, statistics, re, json, platform
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from kass_layer.detector.engine import Detector, tokenize
from kass_layer.detector.unify import unify
t0=time.perf_counter(); det = Detector(ROOT / "demo_local"); load=time.perf_counter()-t0
html=open(ROOT / "demo_local/index.html",encoding="utf-8").read()
ex=re.findall(r'text:\s*"([^"]{40,})"', html)
base=" ".join(ex) if ex else ""
base += " درّبنا المودل على بيانات العملاء، ثم قارنّا الموديل الجديد بالنموذج القديم. رفعنا الملفات على الدرايف، ثم شاركنا رابط الدرايف مع الفريق، وحفظنا نسخة في Drive."
words=base.split()
print("examples",len(ex),"base words",len(words),"load s",round(load,2))
def med(f,n=15):
    f(); xs=[]
    for _ in range(n):
        a=time.perf_counter(); f(); xs.append((time.perf_counter()-a)*1000)
    return statistics.median(xs)
out=[]
for N in (50,150,300,600,1000):
    t=" ".join((words*(N//len(words)+1))[:N])
    a=med(lambda: det.analyse(t,"tech"))
    res=det.analyse(t,"tech")
    u=med(lambda: unify(det,t,"tech",analysis=res))
    full=med(lambda: unify(det,t,"tech"))
    out.append(dict(words=N,analyse=round(a,1),unify_only=round(u,1),unify_full=round(full,1),items=len(res["items"])))
    print(out[-1])
print(platform.processor())
json.dump(out,open(sys.argv[1],"w"))
