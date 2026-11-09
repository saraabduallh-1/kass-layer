# Speed of the detector (2026-11-09)

Texts: the first N characters of the 32 real articles (`logs/real_articles/*.json`, all domains), analysed in the tech
domain; median of 5 runs after one warm-up. Office PC (Windows 11, Python 3.11, Node 20). Server: kass.arai.center,
timed from the office PC, so each request includes ~0.33 s network round trip (a 5-character request takes 0.33 s).

| Text | Words | Page engine (JS, as in the browser) | Python engine (PC) | API on the server (incl. network) |
|---|---|---|---|---|
| 300 chars | 44 | 1.7 ms | 2.9 ms | 0.32 s |
| 1,000 chars | 146 | 19 ms | 45 ms | 0.53 s |
| 5,000 chars (API maximum) | 800 | 0.20 s | 1.19 s | 3.15 s |
| 20,000 chars | 3,251 | 1.34 s | 4.65 s | (over the API limit) |

- One real article (~1,040 chars), Python on the PC: median 0.16 s, slowest 0.97 s.
- Loading the indices: page engine 0.53 s, Python 1.24 s (once, at start).
- Opening the live site to the first result (fresh browser, office network): 2.0–2.2 s; 4.8 MB transferred (index.json
  is 13 MB, served gzip-compressed at 4.4 MB). All data in demo_local: 36.4 MB, 17.2 MB gzipped.
- Bottleneck: on 5,000 characters ~90% of the Python time is the phonetic fallback (`phonetic()`, 104 calls, ~283,000
  Counter intersections). The JS engine does the same work 6× faster. Optimising it (keeping parity 212/212) is the
  obvious next step if the API must take long texts quickly.
