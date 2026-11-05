# -*- coding: utf-8 -*-
"""A/B of the fill guide: the full topic texts in the system prompt against core + map + read_topics
(translator.guide, 2026-11-05). The yardstick is the studio's own catalogue: each example carries the question it
answers (ask_en) and the document that answers it; the translator sees ONLY the question, the core judges both
documents, and a case MATCHES when the translator's document gets the same primary verdict as the catalogue's.

    python3 bench/fill_guide_ab.py --provider nvidia --n 12 --out bench/fill_guide_ab.json

Free models only (the curator: NVIDIA is the free resource; Groq has a 200k-token daily limit; an Anthropic key spends
his money and is never used here). Cases: every catalogue example that uses a document field (bounds, sets) plus a
spread over the kinds. The result decides whether ZTL_FILL_GUIDE=map is switched on; nothing in the studio changes.
"""
import argparse, json, os, sys, time
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import translator, zfl, zflexamples as X          # noqa: E402

MODELS = {"nvidia": ["nvidia/nemotron-3-ultra-550b-a55b", "nvidia/nemotron-3.5-lightning-30b-a3b"],
          "groq": ["openai/gpt-oss-120b", "qwen/qwen3.8-27b"]}


def primary(doc):
    """the verdict a person reads first: refused, or the instruments' dispositions and the passport kinds"""
    try:
        r = zfl.run(doc)
    except Exception as e:
        return ("CRASH", type(e).__name__)
    if not r.get("ok"):
        return ("REFUSED",)
    rep, out = r["report"], []
    for k in ("numeric", "judge"):
        v = rep.get(k)
        if isinstance(v, dict) and (v.get("disposition") or v.get("verdict")):
            out.append((k, v.get("disposition") or v.get("verdict")))
    p = rep.get("passport")
    if isinstance(p, list) and p:
        out.append(("passport", tuple(sorted({str(x.get("kind")) for x in p if isinstance(x, dict)}))))
    b = rep.get("bounds")
    if isinstance(b, list) and b:
        out.append(("bounds", tuple(str(x.get("verdict")) for x in b if isinstance(x, dict))))
    s = rep.get("sets")
    if isinstance(s, dict):
        out.append(("sets", tuple(sorted(str(c.get("disposition")) for c in s.get("claims", []) if isinstance(c, dict)))))
    return tuple(out) or ("NOTHING",)


def cases(n):
    ex = [(i, e) for i, e in enumerate(X.EXAMPLES) if e.get("ask_en")]
    fields = [(i, e) for i, e in ex if any(e["doc"].get(k) for k in ("sets", "bounds", "grounds"))]
    rest, seen = [], {}
    for i, e in ex:
        if (i, e) in fields:
            continue
        if seen.get(e["kind"], 0) < 3:
            rest.append((i, e)); seen[e["kind"]] = seen.get(e["kind"], 0) + 1
    return (fields + rest)[:n]


def run_one(ask, prov, mode):
    os.environ["ZTL_FILL_GUIDE"] = mode
    last = None
    for model in MODELS[prov]:
        t = time.time()
        try:
            r = translator.fill([{"role": "user", "content": ask}], lang="en", cfg={"provider": prov, "model": model})
            return {"model": model, "ok": r.get("ok"), "doc": r.get("doc"), "topics": r.get("topics_read"),
                    "seconds": round(time.time() - t, 1)}
        except Exception as e:
            last = f"{model}: {str(e)[:160]}"
    return {"ok": False, "error": last}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="nvidia")
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--out", default=os.path.join(HERE, "bench", "fill_guide_ab.json"))
    a = ap.parse_args()
    rows = []
    for i, e in cases(a.n):
        want = primary(e["doc"])
        row = {"example": i, "kind": e["kind"], "label": e["en"], "ask": e["ask_en"], "want": want}
        for mode in ("full", "map"):
            got = run_one(e["ask_en"], a.provider, mode)
            got["verdict"] = primary(got["doc"]) if got.get("doc") else ("NO DOCUMENT",)
            got["match"] = got["verdict"] == want
            row[mode] = got
        rows.append(row)
        json.dump(rows, open(a.out, "w"), indent=1, default=str, ensure_ascii=False)
        print(f"{i:2d} {e['kind']:9s} full={'MATCH' if row['full']['match'] else 'miss '} "
              f"map={'MATCH' if row['map']['match'] else 'miss '} topics={row['map'].get('topics')} "
              f"| {e['en'][:40]}", flush=True)
    for mode in ("full", "map"):
        m = sum(r[mode]["match"] for r in rows)
        print(f"{mode}: {m}/{len(rows)} match the catalogue's verdict")
