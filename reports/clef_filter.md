# Detector with and without the context rules, with and without Clef-Flash

## with the two rules: threshold chosen on the tuning sets = 0.4

| gold set | no filter R/P | Clef filter R/P | extra no filter | extra filter |
|---|---|---|---|---|
| gold-tuning | 93.8 / 88.2 | 91.7 / 93.6 | 6 | 3 |
| gold-ambiguity | 71.4 / 62.5 | 64.3 / 60.0 | 2 | 2 |
| gold-arabic-tuning | 67.7 / 67.7 | 67.7 / 70.0 | 10 | 9 |
| gold-heldout-1 | 81.0 / 65.4 | 81.0 / 65.4 | 6 | 6 |
| gold-heldout-2 | 94.7 / 100.0 | 94.7 / 100.0 | 0 | 0 |
| gold-arabic-heldout | 66.7 / 61.5 | 66.7 / 61.5 | 5 | 5 |
| gold-written | 67.9 / 67.9 | 67.9 / 79.2 | 7 | 4 |
| gold-wiki | 0.0 / 0.0 | 0.0 / 0.0 | 33 | 28 |

## without the rules: threshold chosen on the tuning sets = 0.4

| gold set | no filter R/P | Clef filter R/P | extra no filter | extra filter |
|---|---|---|---|---|
| gold-tuning | 93.8 / 86.5 | 91.7 / 91.7 | 7 | 4 |
| gold-ambiguity | 71.4 / 58.8 | 64.3 / 56.2 | 3 | 3 |
| gold-arabic-tuning | 67.7 / 53.8 | 67.7 / 58.3 | 18 | 15 |
| gold-heldout-1 | 81.0 / 63.0 | 81.0 / 63.0 | 7 | 7 |
| gold-heldout-2 | 94.7 / 100.0 | 94.7 / 100.0 | 0 | 0 |
| gold-arabic-heldout | 83.3 / 52.6 | 83.3 / 58.8 | 9 | 7 |
| gold-written | 71.4 / 57.1 | 71.4 / 69.0 | 13 | 8 |
| gold-wiki | 0.0 / 0.0 | 0.0 / 0.0 | 44 | 31 |
