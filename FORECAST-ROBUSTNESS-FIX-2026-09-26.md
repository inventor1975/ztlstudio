# FORECAST — fixing the robustness findings (frozen BEFORE the change)

**Date:** 2026-09-26. **Written by:** Claude (Opus 5.5), curator Vitaly Reznik («Да, как скажешь»).
**Source:** the cloud red team, `REDTEAM-ROBUSTNESS-2026-09.md` (branch
redteam/studio-robustness-2026-09); all six findings reproduced locally first (stand RED 6/9).

## F4 — measured further before writing this (local, `zfl.run`, worst over hash seeds)
The cost is the core's completion table over READING atoms, and a comparison is such an
atom although `names_in` sees only its one name. Worst CPU over 10–20 seeds:

| reading atoms | worst |
|---|---|
| 10 propositional (xor chain) | 0.01 s |
| 8 comparisons | 0.59 s |
| 9 = 7 comparisons + 2 props | 0.53 s |
| 10 = 10 comparisons | 2.83 s |
| 10 = 8 comparisons + 2 props | **8.33 s** |

Change: the cap counts reading atoms = propositional names outside comparisons + distinct
comparisons (found by the judge's own splitter). Cap stays 10 when there is no comparison
(unchanged behaviour), and is **9** when there is at least one.

## F5 — `to_system` asks `names_in` of every defined ground for every row
Change: the names the defined grounds mention are collected ONCE; membership is a set lookup.

## F1, F2, F3, F6 and the judge's missing rate limit — in `ztlstudio.py do_POST`
- any failure to decode the body (RecursionError, ValueError, …) → 400 "bad json";
- a negative Content-Length → 400;
- a body that is valid JSON but not an object → 400 with a clean message;
- `/api/v2run` and `/api/v2validate` get a per-visitor limit, 30 a minute (the API's rate).
  The page calls the judge on a button press, not on typing, so a person never meets it.

## Predictions
- **P1:** `test_redteam_robustness.py` GREEN (9/9).
- **P2:** `test_zfl.py` GREEN — every catalogue example still validates (none uses > 9 reading
  atoms with a comparison; the largest uses 5).
- **P3:** the 800-row table: 16 s → under 0.5 s CPU; 1500 rows under 1 s.
- **P4:** a 10-comparison claim now gets E_TOOBIG; a 9-atom one passes; 10 plain atoms pass.
- **P5:** ZTL `run_all.py` unaffected (the change is in the studio); API tests GREEN after
  the copy is refreshed.
