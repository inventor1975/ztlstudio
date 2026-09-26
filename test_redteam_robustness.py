# -*- coding: utf-8 -*-
"""
test_redteam_robustness — ZTLStudio must survive hostile requests (2026-09-26).

LOCAL ONLY. Starts its own public-mode server on 127.0.0.1 with a scrubbed
environment and empty HOME (no provider key anywhere), and sends no `cfg`, so
the AI routes never reach the network. Nothing leaves the machine.

Each check asserts the behaviour a hardened server WOULD give, so the stand is
RED on the current code (6c449ee) — it pins six findings — and turns green when
they are fixed. The fixes are decided separately; no server or core code is
touched here.

Findings pinned (see REDTEAM-ROBUSTNESS-2026-09.md):
  F1  deeply nested JSON  -> RecursionError in json.loads (do_POST:607, outside
      the catch-all) -> the worker thread dies, the client gets NO response.
  F2  a JSON integer literal with > 4300 digits -> ValueError (int-string limit)
      at the same line, same result. ~4.3 KB body, far under the 256 KB cap.
  F3  Content-Length: -1 (or a huge CL with a short body) -> the size check
      `n > 262144` is skipped, rfile.read(n) blocks, the worker hangs. Held
      connections pile up unbounded threads on ThreadingHTTPServer, bypassing
      the body cap entirely.
  F4  many comparisons over ONE numeric name pass validation with no E_TOOBIG
      (the cap counts distinct NAMES, `names_in`), yet the core enumerates the
      completion table over every comparison -> unbounded server CPU.
  F5  a table of cross-referencing rows: zfl.to_system is O(rows^2), so a 99 KB
      body (under the cap, no E_TOOBIG) burns > 2 s of one core (16 s measured;
      182 KB -> 57 s). The audit's "rows are NOT capped / cheap" does not hold
      for `defined` rows that reference others.
  F6  a non-dict JSON payload (null, 5, "x") -> AttributeError caught by the
      catch-all -> "internal studio error" (E_INTERNAL) instead of a clean
      validation issue.

Run: python3 test_redteam_robustness.py   ->  ROBUSTNESS GREEN, or RED naming each.
"""
import json
import os
import socket
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import redteam_robustness as R          # noqa: E402

PORT = 8198
CHECKS, FAILS = 0, []


def check(cond, what):
    global CHECKS
    CHECKS += 1
    if not cond:
        FAILS.append(what)
        print(f"FAIL: {what}")


def status(body, cl=None, timeout=6.0, path="/api/v2run"):
    st, wall, raw = R.send(PORT, body, path, cl, timeout)
    return st, wall, raw


def cpu_now(pid):
    return R.proc_cpu(pid)


def main():
    proc, home = R.start_server(PORT)
    pid = proc.pid
    try:
        # ---- F1: deep JSON nesting -> the server should answer 400, not vanish
        st, _, _ = status("{\"doc\":" + "[" * 2000 + "]" * 2000 + "}", timeout=6)
        check(isinstance(st, int) and st == 400,
              f"F1 deep JSON nesting returns a clean 400 (got {st}); "
              f"NO-RESPONSE means an uncaught RecursionError killed the worker")
        check(proc.poll() is None, "F1 server still alive")

        # ---- F2: giant integer literal -> should be 400, not a dead worker
        st, _, _ = status('{"doc":{"n":' + "9" * 5000 + "}}", timeout=6)
        check(isinstance(st, int) and st == 400,
              f"F2 5000-digit integer literal returns a clean 400 (got {st}); "
              f"NO-RESPONSE means an uncaught ValueError killed the worker")

        # ---- F3: negative Content-Length -> reject fast, do not hang the worker
        small = json.dumps({"doc": {"claim": "a",
                                    "rows": [{"name": "a", "status": "unverified"}]}})
        st, wall, _ = status(small, cl="-1", timeout=4)
        check(isinstance(st, int) and st in (400, 413),
              f"F3 Content-Length:-1 is rejected (got {st} after {wall}s); "
              f"TIMEOUT means read(-1) hung the worker and the body cap was bypassed")

        # ---- F4: many comparisons, one name -> the cap must bound the cost
        claim = " ^ ".join(f"(x <= {j})" for j in range(1, 15))
        import zfl
        codes = [i["code"] for i in zfl.validate(
            {"claim": claim, "rows": [{"name": "x", "means": "x",
             "status": "unverified", "value": "[0,50]"}]})]
        check("E_TOOBIG" in codes,
              f"F4 a 14-comparison claim over one name is capped (validate codes "
              f"{codes}); the completion table is 3**comparisons, unbounded by the "
              f"name-count cap")

        # ---- F5: cross-referencing rows -> under-cap body must not exceed 2s CPU
        rows = [{"name": "a", "means": "a", "status": "unverified"}]
        rows += [{"name": f"d{i}", "means": "d", "status": "defined", "ground": "a"}
                 for i in range(800)]
        rows += [{"name": f"u{i}", "means": "u", "status": "unverified"}
                 for i in range(800)]
        body = json.dumps({"doc": {"claim": "a", "rows": rows}})
        check(len(body) < R.CAP, f"F5 body {len(body)}B is under the {R.CAP}B cap")
        R.reset_hwm(pid)
        c0 = cpu_now(pid)
        status(body, timeout=4.5)          # client gives up; server keeps computing
        # by 4.5 s wall a single-threaded CPU-bound request has already burned >2s
        burned = cpu_now(pid) - c0
        check(burned <= 2.0,
              f"F5 an under-cap {len(body)//1024}KB table stays within 2s server "
              f"CPU (burned {burned:.1f}s by 4.5s wall); rows are effectively "
              f"uncapped and to_system is O(rows^2)")

        # ---- F6: non-dict payload -> a clean validation error, not E_INTERNAL
        st, _, raw = status("null", timeout=4)
        check(not R.is_internal(raw),
              "F6 a non-dict JSON payload yields a clean issue, not "
              "'internal studio error' (E_INTERNAL from an uncaught AttributeError)")

        # ---- a small seeded sweep: no OTHER dead worker / 5xx / >2s slips through
        extra = 0
        for gname in ("json", "types", "names"):
            import random
            rnd = random.Random(f"{gname}:stand-20260926")
            for label, b, path, cl in list(R.GENERATORS[gname](rnd))[:40]:
                r = R.measure(proc, PORT, b, path, cl, 6.0)
                if not r["alive"]:
                    proc, home2 = R.start_server(PORT)
                    pid = proc.pid
                if "DEAD" in R.flags(r) or "HTTP5xx" in R.flags(r):
                    extra += 1
                    print(f"  sweep hit: {gname}/{label}: {r['status']}")
        check(extra == 0, f"the seeded sweep found {extra} unexpected dead/5xx responses")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        import shutil
        shutil.rmtree(home, ignore_errors=True)

    if FAILS:
        print(f"\nROBUSTNESS RED: {len(FAILS)} of {CHECKS} checks fail (findings "
              f"present on this code) — see above")
        sys.exit(1)
    print(f"\nROBUSTNESS GREEN ({CHECKS} checks)")


if __name__ == "__main__":
    main()
