# RED TEAM — ZTLStudio robustness (2026-09-26)

**Target:** a LOCAL copy of `ztlstudio.py` at `6c449ee`, run exactly as production
does — `ZTLSTUDIO_PUBLIC=1 PORT=8195 python3 ztlstudio.py` — with **no provider
key anywhere** (scrubbed environment, empty `HOME`) and **no `cfg` in any
request**, so the AI routes stop at `translator.llm` before any network call.
Every request went to `127.0.0.1`. No request was sent to any public host.

**What was looked for:** a request that (a) crashes the process, (b) returns
HTTP 500 / an unhandled exception, (c) burns > 2 s of server CPU, (d) grows
memory without bound, or (e) bypasses a stated limit (body cap, `E_TOOBIG`,
rate limit, public-mode refusals).

**Result: six findings.** None crashes the process (the server is threaded and
survives), but three leave a request with **no HTTP response** because an
exception escapes the handler's catch-all, one **hangs a worker and bypasses
the 256 KB body cap**, and two **burn unbounded CPU under the caps** — the
`E_TOOBIG` guard and the audit's "rows are cheap" claim do not cover them. The
stated defences that DO hold are listed at the end.

`ztlstudio.py`, `zfl.py` and `ztlcore/` are untouched. The stand
`test_redteam_robustness.py` fails on this code, pinning each finding; fixes are
decided separately.

---

## Findings

Severity is for the public instance behind Apache. "Reachable" means a single
well-formed HTTP request under the 256 KB cap; the Apache caveat is called out
where it matters.

| # | class | endpoint | what | severity |
|---|---|---|---|---|
| F1 | (b) uncaught exception, no response | any POST | deeply nested JSON → `RecursionError` in `json.loads` | MEDIUM |
| F2 | (b) uncaught exception, no response | any POST | a JSON integer > 4300 digits → `ValueError` in `json.loads` | MEDIUM |
| F3 | (d)+(e) worker hang, body-cap bypass | any POST | `Content-Length: -1` (or huge CL, short body) hangs the worker; held connections pile unbounded threads | MEDIUM |
| F4 | (c)+(e) CPU, `E_TOOBIG` bypass | `/api/v2run` | many comparisons over ONE numeric name: the cap counts names, the core enumerates the completion table | MEDIUM |
| F5 | (c)+(e) CPU, "rows are cheap" false | `/api/v2run` | cross-referencing rows: `zfl.to_system` is O(rows²); 99 KB body → 16 s CPU | MEDIUM |
| F6 | (b) caught, disclosure-shaped | `/api/v2run`, `/api/v2validate` | a non-dict JSON payload → `E_INTERNAL` ("internal studio error") not a clean issue | LOW |

### F1 — deeply nested JSON kills the worker with no response

`do_POST` parses the body at line 607:

```python
payload = json.loads(self.rfile.read(n).decode() or "{}")
```

wrapped in `except (json.JSONDecodeError, UnicodeDecodeError)`. Deeply nested
JSON makes the decoder recurse, and it raises **`RecursionError`**, which is
neither of those, so it escapes `do_POST` entirely (the catch-all that wraps
`fn(payload)` is later, at line 612). `socketserver` logs the traceback and
closes the socket; the client gets no status line.

Minimal (2 KB body, far under the 256 KB cap):

```
POST /api/v2run   body = {"doc":[[[[ … 2000 deep … ]]]]}
-> connection closed, NO HTTP RESPONSE
server log: RecursionError: maximum recursion depth exceeded while decoding a JSON array
```

Server stderr, verbatim:

```
File ".../ztlstudio.py", line 607, in do_POST
    payload = json.loads(self.rfile.read(n).decode() or "{}")
RecursionError: maximum recursion depth exceeded while decoding a JSON array from a unicode string
```

The process survives (one thread dies). The cost to the attacker is one tiny
request per failed response.

### F2 — a long integer literal kills the worker with no response

Same line, same escape, different exception. Python 3.11 caps integer↔string
conversion at 4300 digits; a JSON number with more digits raises a plain
**`ValueError`** inside `json.loads` (not a `JSONDecodeError`), so it escapes.

Minimal (~4.3 KB body):

```
POST /api/v2run   body = {"doc":{"n": 999…9}}   (5000 nines)
-> NO HTTP RESPONSE
server log: ValueError: Exceeds the limit (4300 digits) for integer string conversion
```

The threshold is 4301 digits; anything longer triggers it.

### F3 — negative / oversized Content-Length hangs the worker and bypasses the body cap

The size guard is:

```python
try:    n = int(self.headers.get("Content-Length", 0))
except (TypeError, ValueError): ... 400
if n > 262144: ... drain ... 413
payload = json.loads(self.rfile.read(n).decode() or "{}")
```

`int("-1")` is `-1`, which passes the `except` and is **not** `> 262144`, so no
413. Then `rfile.read(-1)` reads **until EOF** — and the attacker never closes
the socket, so the worker blocks forever holding a thread. The 256 KB body cap
is bypassed completely: the check only compares against a positive `n`.

Measured — 60 connections, each `Content-Length: -1` with a 2-byte body, held
open:

```
threads before: 1
threads after 60 held CL:-1 connections: 61      (all stuck in read(-1))
a normal request meanwhile: 200                  (threaded, so still served…)
```

`ThreadingHTTPServer` spawns an unbounded thread per connection, so an attacker
holding N cheap connections pins N threads and their stacks — memory grows with
N (category d), and the body-size DoS guard is defeated (category e). The same
hang occurs with a large positive `Content-Length` and a short body: the drain
loop `rfile.read(min(remaining, 65536))` blocks waiting for bytes that never
come (`headers/CL huge, small body` and `headers/2MB body, CL=-1` both TIMEOUT
in the sweep).

**Apache caveat:** behind the production reverse proxy, Apache may reject a
negative `Content-Length` before it reaches the app; the app itself is
vulnerable, and the audit's own drain-before-413 logic shows the app is meant to
be correct about raw framing regardless. A slowloris-style hold with a valid
large CL is not proxy-specific.

### F4 — many comparisons over one name bypass `E_TOOBIG` and burn CPU

`zfl.validate` caps **distinct atoms** at `MAX_ATOMS = 10`, counted by
`names_in`, with the comment "cost is 3\*\*atoms". But a numeric comparison like
`x <= 3` is one atom to `names_in` (the single name `x`) and a **separate** atom
to the core's completion-table enumeration. So a chain of many comparisons over
ONE name is "1 atom" to the cap and passes, while the core enumerates the table
over every comparison.

```
claim = (x <= 1) ^ (x <= 2) ^ … ^ (x <= 14)     # 156 bytes, names_in = 1
validate() -> []                                 # no E_TOOBIG
```

Server CPU, measured in the seeded run (`value = [0,50]`):

```
xor-chain, 10 comparisons -> 7.10 s CPU  (HTTP 200)
xor-chain, 13 comparisons -> 7.94 s CPU  (client TIMEOUT; server keeps computing)
```

The exact cost is **hash-seed dependent** (the fixed-point/grade search prunes
by set iteration order): repeated direct runs of the 12-comparison claim gave
0.24 s, 2.05 s and 5.70 s of CPU on the same input. Variable, but it exceeds 2 s
readily and is unbounded in the claim length that the cap lets through. Because
`http.server` has no request-CPU limit, the work continues after the client
disconnects, so one ~150-byte request occupies a core for seconds with no way to
cancel it.

### F5 — a table of cross-referencing rows is O(rows²), under every cap

`zfl.to_system` decides, for each row, whether any defined row's ground mentions
it:

```python
if any(r["name"] in names_in(d.get("ground") or "")
       for d in defined.values()):
```

`names_in` re-parses each ground with regexes on every call, so a table with D
`defined` rows and U other rows costs O(D·(D+U)) `names_in` calls. Rows are not
capped at all (only atoms-in-formulas are), so this is reachable under the 256 KB
body cap.

Measured over HTTP (server CPU to completion):

```
 800 defined + 800 plain rows   99 KB body   ->  16.2 s CPU   (no E_TOOBIG)
1500 defined + 1500 plain rows  182 KB body  ->  57.2 s CPU
2500 + 2500                     305 KB body  ->  (over the 256 KB cap; rejected 413)
```

The profile of the 800-row case: `zfl.to_system` 15.5 s of 15.7 s total, inside
2.56 M calls to `names_in` → `re.sub`/`re.findall`. This directly contradicts
`SECURITY-AUDIT.md` ("rows are NOT capped… a hundred-row table whose formulas
each speak of six atoms reads in 0.003 s"): that holds for independent rows, not
for `defined` rows that reference others, which the studio's own examples use.

### F6 — a non-dict JSON payload returns "internal studio error"

`api_v2run`/`api_v2validate` do `payload.get("doc")`. A JSON body that is a valid
document but not an object — `null`, `5`, `"x"`, `[1,2,3]`, `true` — makes
`payload` a non-dict, so `.get` raises `AttributeError`, caught by the catch-all,
returned as `E_INTERNAL` "internal studio error — the detail is in the server
log". Nine such inputs hit it in the sweep. It is caught (no crash, HTTP 200),
but a well-formed request gets an opaque internal-error answer instead of a clean
validation issue — the shape the audit's finding #2 was about. Low severity.

---

## What was tried, and the counts

Everything is seeded; a generator's cases come from `random.Random(f"{name}:{seed}")`
with `seed = 20260926`. Bodies are raw HTTP/1.1 POSTs so the framing itself
(Content-Length, non-UTF-8, truncation) can be attacked, not just the JSON.

`python3 redteam_robustness.py --seed 20260926 --timeout 8 --out rr_full.json`
— 141 requests, server base RSS 21.6 MB, 18 flagged:

| generator | requests | what it covers |
|---|---|---|
| json | 14 | malformed/truncated/non-UTF-8 JSON, bare scalars, duplicate keys, deep nesting, 200 K-digit int, unicode escapes |
| headers | 9 | Content-Length: negative, omitted, zero, huge, non-numeric, float; 2 MB bodies honest and spoofed |
| types | 42 | wrong type in every field (doc/rows/row/claim/ask/grounds/value/name/status/sentences/atoms), non-dict payloads, on both v2run and v2validate |
| formula | 12 | xor-chains of comparisons (1 atom), deep nested connectives (2 atoms), high-degree polynomials on wide int boxes, multilinear sample products, sqrt/division chains, formulas at 4000/4096/4200/20000 chars |
| rows | 4 | 200–2500 defined+plain rows, 6000 plain rows, one 200 K-char name |
| names | 60 | RTL / zero-width / NUL / surrogate / combining / BOM unicode in names and claims; `10**100000`, 100 K-digit ints, `1e100000`, nan/inf spellings, `1/0`, giant fractions as values and in claims; scale-field edge cases; all-operators claim |

Flag totals: `E_INTERNAL` 9 (F6), `NO-RESPONSE` 3 (F1, F2), `TIMEOUT` 4 (F3),
`SLOW-CPU` 3 (F4 ×2, F5 ×1). Peak RSS across all 141 requests stayed ≤ 36 MB, so
no single request grew memory without bound (the memory vector is F3's thread
pile-up, not one request). No request killed the process.

Worst by server CPU (from the run):

```
  7.94 s  TIMEOUT  formula/xor-chain 13 comparisons, 1 name     (F4)
  7.10 s  200      formula/xor-chain 10 comparisons, 1 name     (F4)
  2.14 s  200      rows/200 defined + 200 plain rows            (F5, small instance)
  0.85 s  200      formula/formula 3847 chars, 1 atom
```

## Stated defences that HOLD (checked, with evidence)

- **256 KB body cap** — an honest 2 MB body gets `413` with the body drained
  first (no Apache desync). Only defeated by the framing bug F3.
- **`E_TOOBIG` on ≥ 11 distinct atoms** — a propositional formula over 11+ named
  atoms is refused before the expensive read. The bypasses F4/F5 use ONE name /
  many rows, which the cap does not count.
- **4096-char formula cap** — a 20 000-char claim is refused `E_TOOLONG`; the
  under-cap 3847-char product took 0.85 s.
- **Public-mode refusals** — `/api/savekey` returns "saving is off" and writes
  nothing; the AI routes fail closed with no key (no `cfg`, no env, empty HOME),
  never reaching the network.
- **Catch-all disclosure** — `fn(payload)` exceptions return the exception TYPE
  only (`E_INTERNAL`), not paths or input (audit finding #2). F1/F2 slip past it
  only because they fire in `json.loads`, before the guarded call.
- **No code execution** — no `eval`/`exec`/`os.system` in the request path
  (unchanged from the audit).
- **Non-UTF-8 / bad JSON / bad Content-Length** — clean `400`. Rate limit and
  path traversal were not re-exercised (no key; `/static/` uses `basename`).

## Limits of this search (say what was NOT covered)

- Only `/api/v2run`, `/api/v2validate`, and the framing of any POST were fuzzed
  in depth. The LLM routes (`/api/v2fill`, `/api/v2comment`) were exercised only
  to confirm they fail closed without a key; their behaviour WITH a provider is
  out of scope by instruction.
- The rate limiter was not stress-tested (it gates only the LLM routes, which are
  keyless here).
- Apache/TLS termination, and whether the proxy filters F3's negative
  Content-Length, were not tested — local app only.
- Numeric-judge correctness is a separate red team (`ZTL/inventory/probes/
  REDTEAM-NUMERIC-2026-09.md`); this pass is robustness/DoS only.
- "Found none" for process crashes and single-request memory blowup means none
  in the space above.

## Reproduce every number

```sh
cd ztlstudio
python3 test_redteam_robustness.py                       # the stand: RED, 6 of 9 checks, ~12 s
python3 redteam_robustness.py --seed 20260926 --out rr_full.json   # the full sweep, 141 requests
python3 redteam_robustness.py --only formula --n 12      # just the CPU generators
python3 redteam_robustness.py --only headers             # the Content-Length cases (F3)
```

The stand and the fuzzer both start their own local public-mode server with a
scrubbed environment; neither needs a key and neither touches the network.
