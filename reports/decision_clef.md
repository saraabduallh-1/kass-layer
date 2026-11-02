# Decision test — Clef-Flash (4-bit), same cases as decision_gemma

600 cases, accuracy at 0.5: 0.657, 0.211 s per case.

| p >= | kept | precision | recall | wrong kept |
|---|---|---|---|---|
| 0.5 | 484 | 0.597 | 0.963 | 195 |
| 0.6 | 467 | 0.612 | 0.953 | 181 |
| 0.7 | 443 | 0.625 | 0.923 | 166 |
| 0.8 | 408 | 0.637 | 0.867 | 148 |
| 0.9 | 294 | 0.704 | 0.69 | 87 |
| 0.95 | 78 | 0.718 | 0.187 | 22 |
| 0.99 | 0 | None | 0.0 | 0 |
