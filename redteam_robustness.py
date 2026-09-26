# -*- coding: utf-8 -*-
"""
redteam_robustness — seeded local robustness measurement of ZTLStudio.

Local only: starts its own server on 127.0.0.1 in public mode with a scrubbed
environment (no provider key), and never sends a `cfg`, so the AI routes stop
before any network call. Measures per request: HTTP status, client wall time,
server CPU seconds (/proc/<pid>/stat), and peak RSS (VmHWM after clear_refs).

Run: python3 redteam_robustness.py --seed 20260926 --out /tmp/rr.json
     python3 redteam_robustness.py --only formula --n 300
"""
import argparse
import json
import os
import random
import shutil
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CAP = 262144          # the server's stated body cap
PORT = int(os.environ.get("RR_PORT", "8196"))


def clock_tick():
    return os.sysconf("SC_CLK_TCK")


def proc_cpu(pid):
    """utime + stime of a process in seconds, or None if it is gone."""
    try:
        parts = open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()
        return (int(parts[11]) + int(parts[12])) / clock_tick()
    except Exception:
        return None


def proc_hwm_kb(pid):
    try:
        for line in open(f"/proc/{pid}/status"):
            if line.startswith("VmHWM:"):
                return int(line.split()[1])
    except Exception:
        return None
    return None


def reset_hwm(pid):
    try:
        open(f"/proc/{pid}/clear_refs", "w").write("5")
        return True
    except Exception:
        return False


def start_server(port=PORT):
    """Start a local public-mode server with a scrubbed env and empty HOME."""
    home = tempfile.mkdtemp(prefix="rr_home_")
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
           "ZTLSTUDIO_PUBLIC": "1", "PORT": str(port),
           "HOME": home, "LANG": "C.UTF-8"}
    proc = subprocess.Popen([sys.executable, "ztlstudio.py"], cwd=HERE, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
            return proc, home
        except OSError:
            if proc.poll() is not None:
                raise RuntimeError("server exited: " + proc.stderr.read().decode()[:500])
            time.sleep(0.1)
    raise RuntimeError("server did not come up")


def send(port, body, path="/api/v2run", content_length=None, timeout=8.0,
         headers=None):
    """One raw HTTP/1.1 POST. content_length overrides the real length
    (None = real; "omit" = no header; any string = that literal value).
    Returns (status, wall_s, raw_head_bytes)."""
    if isinstance(body, str):
        body = body.encode("utf-8", "surrogatepass")
    hdrs = {"Host": "127.0.0.1", "Content-Type": "application/json"}
    if content_length != "omit":
        hdrs["Content-Length"] = str(len(body) if content_length is None
                                     else content_length)
    hdrs.update(headers or {})
    req = (f"POST {path} HTTP/1.1\r\n"
           + "".join(f"{k}: {v}\r\n" for k, v in hdrs.items()) + "\r\n").encode()
    t = time.time()
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=timeout)
        s.settimeout(timeout)
        s.sendall(req + body)
        data = b""
        while len(data) < 65536:
            try:
                c = s.recv(65536)
            except socket.timeout:
                s.close()
                return "TIMEOUT", round(time.time() - t, 3), data[:200]
            if not c:
                break
            data += c
        s.close()
    except (ConnectionError, OSError) as e:
        return f"CONN:{type(e).__name__}", round(time.time() - t, 3), b""
    wall = round(time.time() - t, 3)
    if not data:
        return "NO-RESPONSE", wall, b""
    try:
        status = int(data.split(b" ", 2)[1])
    except (IndexError, ValueError):
        return "BAD-STATUS", wall, data[:200]
    return status, wall, data[:65536]


def is_internal(raw):
    return b"E_INTERNAL" in raw or b"internal studio error" in raw


# ------------------------------------------------------------- generators
# Each generator yields (label, raw_body_bytes_or_str, path, content_length).
# content_length is None unless the case is specifically about the header.

def _doc(doc):
    return json.dumps({"doc": doc}, ensure_ascii=False)


UNICODE = ["‮", "​", "\u0000", "﻿", "\U0001f4a9",
           "\ud800", "á" * 50, "　", "\r\n", "\t"]
NUMS = ["10**100000", "1" * 100000, "1e100000", "-1e100000", "nan", "inf",
        "-inf", "NaN", "Infinity", "1/0", "0/0", "1" + "0" * 5000,
        "9" * 400 + "/" + "9" * 400, "1/" + "9" * 4000, ".", "1e999999999"]


def gen_json(rnd):
    """Malformed / hostile JSON bodies (the framing, not the document)."""
    yield "empty body", b"", "/api/v2run", None
    yield "not json", b"><<<", "/api/v2run", None
    yield "truncated", b'{"doc":{"rows":[', "/api/v2run", None
    yield "bare array", b"[1,2,3]", "/api/v2run", None
    yield "bare string", b'"hello"', "/api/v2run", None
    yield "bare number", b"123", "/api/v2run", None
    yield "bare null", b"null", "/api/v2run", None
    yield "bare true", b"true", "/api/v2run", None
    yield "duplicate keys", b'{"doc":{"claim":"a"},"doc":{"claim":"b"}}', "/api/v2run", None
    yield "deep array", ("{\"doc\":" + "[" * 4000 + "]" * 4000 + "}"), "/api/v2run", None
    yield "deep object", ('{"doc":' + '{"a":' * 2000 + '1' + '}' * 2000 + '}'), "/api/v2run", None
    yield "non-utf8 body", b'{"doc":{"claim":"\xff\xfe"}}', "/api/v2run", None
    yield "big int literal", ('{"doc":{"n":' + "9" * 200000 + "}}"), "/api/v2run", None
    yield "unicode escapes", '{"doc":{"claim":"' + "\\u0000" * 1000 + '"}}', "/api/v2run", None


def gen_headers(rnd):
    """Content-Length edge cases (the body cap and the drain path)."""
    small = _doc({"claim": "a", "rows": [{"name": "a", "status": "unverified", "means": "a"}]})
    yield "CL negative", small, "/api/v2run", "-1"
    yield "CL omitted", small, "/api/v2run", "omit"
    yield "CL zero, real body", small, "/api/v2run", "0"
    yield "CL huge, small body", small, "/api/v2run", str(10 ** 9)
    yield "CL non-numeric", small, "/api/v2run", "abc"
    yield "CL float", small, "/api/v2run", "3.5"
    big = _doc({"claim": "a", "rows": [{"name": "a", "status": "unverified",
                                        "means": "x" * (2 * 2 ** 20)}]})
    yield "2MB body, honest CL", big, "/api/v2run", None
    yield "2MB body, CL=-1", big, "/api/v2run", "-1"
    yield "2MB body, CL=10", big, "/api/v2run", "10"


def gen_types(rnd):
    """Wrong types in every field the routes read."""
    variants = [
        ("doc as list", {"doc": [1, 2]}),
        ("doc as string", {"doc": "hi"}),
        ("doc as number", {"doc": 5}),
        ("rows as string", {"doc": {"rows": "abc", "claim": "a"}}),
        ("rows as dict", {"doc": {"rows": {"a": 1}, "claim": "a"}}),
        ("row as list", {"doc": {"rows": [[1, 2]], "claim": "a"}}),
        ("row as string", {"doc": {"rows": ["x"], "claim": "a"}}),
        ("claim as list", {"doc": {"rows": [], "claim": [1, 2]}}),
        ("claim as dict", {"doc": {"rows": [], "claim": {"a": 1}}}),
        ("ask as dict", {"doc": {"rows": [{"name": "a", "status": "unverified"}],
                                 "claim": "a", "ask": {"x": 1}}}),
        ("ask as string", {"doc": {"rows": [], "claim": "a", "ask": "verdict"}}),
        ("grounds as list", {"doc": {"rows": [], "claim": "a", "grounds": [1]}}),
        ("value as list", {"doc": {"rows": [{"name": "a", "value": [1, 2], "status": "verified"}], "claim": "a>1"}}),
        ("value as dict", {"doc": {"rows": [{"name": "a", "value": {"x": 1}, "status": "verified"}], "claim": "a>1"}}),
        ("name as number", {"doc": {"rows": [{"name": 5, "status": "unverified"}], "claim": "a"}}),
        ("name as null", {"doc": {"rows": [{"name": None, "status": "unverified"}], "claim": "a"}}),
        ("status as number", {"doc": {"rows": [{"name": "a", "status": 1}], "claim": "a"}}),
        ("sentences as list", {"doc": {"sentences": [1, 2], "genre": "system"}}),
        ("atoms as list", {"doc": {"atoms": [1], "sentences": {"L": "not(Tr(L))"}}}),
        ("payload not dict", [1, 2, 3]),
        ("payload string", "hello"),
    ]
    for label, p in variants:
        yield label, json.dumps(p), "/api/v2run", None
        yield label + " (validate)", json.dumps(p), "/api/v2validate", None


CONNS = ["and", "or", "xor", "xnor", "imp", "not"]
CMP = ["<=", "<", ">=", ">", "=="]


def gen_formula(rnd):
    """Propositional and numeric formulas near and above the cost cliff.
    The atom cap is on DISTINCT atoms; these keep few atoms and grow the
    formula, or push high-degree numeric terms."""
    # one name, xor chain of comparisons: 3**(operator count) readings, 1 atom
    for k in rnd.sample(range(6, 15), 3):
        claim = " ^ ".join(f"(x <= {j})" for j in range(1, k + 1))
        yield (f"xor-chain {k} comparisons, 1 name",
               _doc({"claim": claim, "rows": [{"name": "x", "means": "x",
                     "status": "unverified", "value": "[0,100]"}]}), "/api/v2run", None)
    # nested connectives, two atoms, deep
    for d in rnd.sample(range(8, 16), 2):
        f = "a"
        for _ in range(d):
            f = f"{rnd.choice(CONNS[:-1])}({f}, b)"
        yield (f"nested connective depth {d}, 2 atoms",
               _doc({"claim": f, "rows": [{"name": "a", "means": "a", "status": "unverified"},
                     {"name": "b", "means": "b", "status": "unverified"}]}), "/api/v2run", None)
    # high-degree polynomial in one name, wide integer box
    poly = "*".join(f"(x-{7 * i + 1})" for i in range(rnd.randint(3, 8)))
    yield ("high-degree poly, wide int box",
           _doc({"claim": f"{poly} <= 0", "rows": [{"name": "x", "means": "x",
                 "status": "unverified", "value": "[-1000000000,1000000000]", "scale": "int"}]}), "/api/v2run", None)
    # many-name multilinear via samples
    body = "*".join(["s"] * rnd.randint(6, 11))
    yield ("multilinear sample product",
           _doc({"claim": f"{body} <= 1000000", "rows": [{"name": "s", "means": "s",
                 "status": "unverified", "value": "[-3,5]", "sample": True}]}), "/api/v2run", None)
    # sqrt / division chain
    e = "x"
    for _ in range(rnd.randint(3, 8)):
        e = f"sqrt({e} / (x + {rnd.randint(1,9)}))"
        e = f"({e} - {rnd.randint(1,9)})"
    yield ("sqrt/div chain",
           _doc({"claim": f"{e} <= 1", "rows": [{"name": "x", "means": "x",
                 "status": "unverified", "value": "[1,1000]"}]}), "/api/v2run", None)
    # formula just under and over the char cap
    for chars in (4000, 4096, 4200, 20000):
        g = ("(a | ~a) & " * (chars // 12))[:chars].rstrip(" &")
        yield (f"formula {len(g)} chars, 1 atom",
               _doc({"claim": g, "rows": [{"name": "a", "means": "a", "status": "unverified"}]}), "/api/v2run", None)


def gen_rows(rnd):
    """Many rows: the to_system quadratic, defined rows, huge tables."""
    for n in rnd.sample([200, 800, 1500, 2500], 2):
        rows = [{"name": "a", "means": "a", "status": "unverified"}]
        rows += [{"name": f"d{i}", "means": "d", "status": "defined", "ground": "a"} for i in range(n)]
        rows += [{"name": f"u{i}", "means": "u", "status": "unverified"} for i in range(n)]
        yield (f"{n} defined + {n} plain rows", _doc({"claim": "a", "rows": rows}), "/api/v2run", None)
    # rows that fit the body but are numerous and tiny
    n = 6000
    rows = [{"name": f"r{i}", "means": "r", "status": "unverified"} for i in range(n)]
    yield (f"{n} plain rows", _doc({"claim": "r0", "rows": rows}), "/api/v2run", None)
    # one very long name
    yield ("one 200k-char name",
           _doc({"claim": "a", "rows": [{"name": "a" * 200000, "means": "a", "status": "unverified"}]}), "/api/v2run", None)


def gen_names(rnd):
    """Long names, long formulas, unicode, sheet/value edge cases."""
    for u in UNICODE:
        yield (f"unicode name {u!r}",
               _doc({"claim": "a", "rows": [{"name": f"a{u}b", "means": u, "status": "unverified"}]}), "/api/v2run", None)
        yield (f"unicode claim {u!r}",
               _doc({"claim": f"a {u} b", "rows": [{"name": "a", "means": "a", "status": "unverified"},
                     {"name": "b", "means": "b", "status": "unverified"}]}), "/api/v2run", None)
    for num in NUMS:
        yield (f"num value {num!r}",
               _doc({"claim": "a >= 0", "rows": [{"name": "a", "means": "a",
                     "status": "verified", "ground": "d", "value": num}]}), "/api/v2run", None)
        yield (f"num in claim {num!r}",
               _doc({"claim": f"a <= {num}", "rows": [{"name": "a", "means": "a",
                     "status": "unverified", "value": "[0,1]"}]}), "/api/v2run", None)
    # scale field edge cases
    for sc in ("decimal99", "frac0", "decimal-1", "frac9999999999", "int ", "deci mal2", "​int"):
        yield (f"scale {sc!r}",
               _doc({"claim": "a == 1", "rows": [{"name": "a", "means": "a",
                     "status": "unverified", "value": "[0,2]", "scale": sc}]}), "/api/v2run", None)
    # human-surface syntax via _coerce is only on v1 routes; v2 takes doc. still:
    yield ("claim all operators", _doc({"claim": "not(and(or(xor(xnor(imp(a,b),a),b),a),b))",
           "rows": [{"name": "a", "means": "a", "status": "unverified"},
                    {"name": "b", "means": "b", "status": "unverified"}]}), "/api/v2run", None)


GENERATORS = {"json": gen_json, "headers": gen_headers, "types": gen_types,
              "formula": gen_formula, "rows": gen_rows, "names": gen_names}


# ---------------------------------------------------------------- the runner
SLOW_CPU = 2.0        # the task's threshold: > 2 s of server CPU
MEM_MB = 400          # a single request growing peak RSS past this is flagged


def measure(proc, port, body, path, cl, timeout):
    """One request with CPU and peak-RSS measurement around it."""
    pid = proc.pid
    reset_hwm(pid)
    cpu0 = proc_cpu(pid)
    status, wall, raw = send(port, body, path, cl, timeout)
    alive = proc.poll() is None
    cpu1 = proc_cpu(pid) if alive else None
    hwm = proc_hwm_kb(pid) if alive else None
    cpu = round(cpu1 - cpu0, 3) if (cpu0 is not None and cpu1 is not None) else None
    return {"status": status, "wall": wall, "cpu": cpu,
            "peak_mb": round(hwm / 1024, 1) if hwm else None,
            "internal": bool(is_internal(raw)), "alive": alive,
            "body_bytes": len(body if isinstance(body, bytes) else body.encode("utf-8", "surrogatepass"))}


def flags(r):
    f = []
    if not r["alive"]:
        f.append("DEAD")
    if isinstance(r["status"], int) and r["status"] >= 500:
        f.append("HTTP5xx")
    if r["status"] in ("NO-RESPONSE", "BAD-STATUS") or (isinstance(r["status"], str) and r["status"].startswith("CONN")):
        f.append("NO-RESPONSE")
    if r["status"] == "TIMEOUT":
        f.append("TIMEOUT")
    if r["internal"]:
        f.append("E_INTERNAL")
    if r["cpu"] is not None and r["cpu"] > SLOW_CPU:
        f.append("SLOW-CPU")
    if r["peak_mb"] is not None and r["peak_mb"] > MEM_MB:
        f.append("MEM")
    return f


def run(seed, only, n, timeout, out):
    proc, home = start_server()
    base_rss = proc_hwm_kb(proc.pid)
    results, worst, findings = [], [], []
    counts = {}
    try:
        names = only.split(",") if only else list(GENERATORS)
        for gname in names:
            rnd = random.Random(f"{gname}:{seed}")
            cases = list(GENERATORS[gname](rnd))
            if n:
                cases = cases[:n]
            for label, body, path, cl in cases:
                r = measure(proc, PORT, body, path, cl, timeout)
                r.update({"gen": gname, "label": label, "path": path})
                fl = flags(r)
                r["flags"] = fl
                counts[gname] = counts.get(gname, 0) + 1
                results.append(r)
                if fl:
                    findings.append(r)
                    print(f"  [{'+'.join(fl)}] {gname}/{label}: status={r['status']} "
                          f"cpu={r['cpu']} peak={r['peak_mb']}MB wall={r['wall']}", flush=True)
                if not r["alive"]:
                    print("  server died — restarting", flush=True)
                    try:
                        err = proc.stderr.read().decode()[-2000:]
                    except Exception:
                        err = ""
                    r["stderr_tail"] = err
                    proc, home2 = start_server()
                    shutil.rmtree(home, ignore_errors=True)
                    home = home2
        worst = sorted([x for x in results if x["cpu"] is not None],
                       key=lambda x: -x["cpu"])[:25]
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        shutil.rmtree(home, ignore_errors=True)
    return {"seed": seed, "base_rss_kb": base_rss, "counts": counts,
            "n_results": len(results), "findings": findings, "worst": worst,
            "results": results if out else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", default="20260926")
    ap.add_argument("--only", default=None)
    ap.add_argument("--n", type=int, default=None)
    ap.add_argument("--timeout", type=float, default=8.0)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    rep = run(a.seed, a.only, a.n, a.timeout, a.out)
    print(f"\nseed {a.seed}: {rep['n_results']} requests, base RSS "
          f"{rep['base_rss_kb']} kB, {len(rep['findings'])} flagged")
    print("worst by server CPU:")
    for w in rep["worst"][:12]:
        print(f"  {w['cpu']:>7} s cpu  peak {w['peak_mb']}MB  status {w['status']:>4}  "
              f"{w['gen']}/{w['label']}")
    if a.out:
        with open(a.out, "w") as fh:
            json.dump(rep, fh, indent=1, default=str)
        print(f"written {a.out}")


if __name__ == "__main__":
    main()
