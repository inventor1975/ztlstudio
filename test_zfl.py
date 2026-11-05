# -*- coding: utf-8 -*-
"""
ZFL v2 end to end, with no browser in the way.

The studio is the point of this work, but a language that can only be
exercised through a web page is a language nobody can test. Everything the
form will do — validate a cell, assemble the sheet, decide which
instruments apply, run them — happens here first, headless and under
assert, so the UI can be a view over something already known to work rather
than the only place it works at all.

Run:  python3 tool/test_zfl.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import zfl                                                      # noqa: E402

MIXED = {
    "rows": [
        {"name": "line", "means": "the invoice line", "status": "verified",
         "ground": "inv-17", "value": "1500", "unit": "RUB"},
        {"name": "budget", "means": "the ceiling", "status": "verified",
         "ground": "order-4", "value": "5000", "unit": "RUB"},
        {"name": "rain", "means": "it is raining", "status": "unverified"},
        {"name": "L", "means": "this sentence is false", "status": "defined",
         "ground": "~Tr(L)"},
    ],
    "claim": "line <= budget",
}


def sec1_one_table_three_instruments():
    print("-" * 72)
    print("1. ONE TABLE, AND NOBODY DECLARED A GENRE")
    r = zfl.run(MIXED)
    assert r["ok"], r["issues"]
    print(f"   applies: {r['applies']}")
    assert r["applies"] == {"numeric": True, "passport": True,
                            "ledger": True, "epoch": False, "judge": True,
                            "bounds": False}
    rep = r["report"]
    print(f"   assembled sheet    : {rep['numeric']['sheet']}")
    print(f"   the invoice claim  : {rep['numeric']['disposition']}")
    print(f"   the liar row       : {rep['passport'][0]['kind']} "
          f"({rep['passport'][0]['detail'][:38]}…)")
    assert rep["numeric"]["disposition"] == "EARNED"
    assert rep["passport"][0]["kind"] == "PARADOX"
    print("   Four rows in one table, and two instruments answered without")
    print("   being chosen: the numeric floor compared roubles to roubles,")
    print("   the passport office convicted the liar. In v1 these were two")
    print("   genres, two tabs, and a declaration the writer had to get")
    print("   right before writing anything.")


def sec2_the_cells_are_checked_where_the_eye_is():
    print("-" * 72)
    print("2. ERRORS ADDRESSED TO A CELL, NOT TO A JSON PATH")
    bad = {"rows": [
        {"name": "a", "status": "verified"},
        {"name": "a", "status": "nonsense"},
        {"name": "L", "status": "defined", "ground": "~Tr(nowhere)"},
    ], "claim": "a <= budget"}
    issues = zfl.validate(bad)
    for i in issues:
        if i["level"] == "error":
            print(f"   {i['code']:16} {i['where']:18} {i['hint'][:44]}")
    codes = {i["code"] for i in issues}
    assert {"E_NOGROUND", "E_DUPNAME", "E_STATUS", "E_UNKNOWN_NAME"} <= codes
    print("   A verified name with nothing backing it, a duplicate, a status")
    print("   outside the four, a formula naming a row that does not exist —")
    print("   each answered at the cell the person is looking at. The typo")
    print("   in a name matters most: it is the commonest way to ask a")
    print("   perfectly well-formed question about nothing at all.")


def sec3_the_ledger_appears_when_it_is_wanted():
    print("-" * 72)
    print("3. TODAY'S LEDGER, REACHED FROM THE SAME TABLE")
    doc = {"rows": [
        {"name": "fee", "means": "the fee", "status": "verified",
         "ground": "cert-7", "ground_kind": "certificate", "value": "100"},
        {"name": "base", "means": "the base", "status": "verified",
         "ground": "deed", "value": "80"},
    ], "claim": "base <= fee"}
    r = zfl.run(doc)
    assert r["ok"], r["issues"]
    led = r["report"]["ledger"]
    print(f"   applies: {r['applies']}")
    for cid, v in led["claims"].items():
        print(f"   {cid:6} {v['disposition']:8} {v['assurance']}")
    print(f"   brackets: {led['brackets']}")
    print(f"   {led['naming']['assumption']}")
    assert r["applies"]["ledger"]
    assert led["claims"]["fee"]["assurance"]["under_expiry"] == "exposed"
    assert led["claims"]["base"]["assurance"]["under_expiry"] == "plain"
    print("   One dropdown — 'kind of ground: certificate' — and the whole")
    print("   of this morning's work arrives: the assurance frame, the trust")
    print("   brackets, the naming assumption printed beside them. The user")
    print("   never learns a syntax for any of it.")


def sec3b_what_the_ground_column_is_actually_for():
    print("-" * 72)
    print("3b. WHY THE GROUND NAME IS NOT DECORATION")
    apart = {"rows": [
        {"name": "a", "means": "first line", "status": "verified",
         "ground": "inv-17", "value": "100"},
        {"name": "b", "means": "second line", "status": "verified",
         "ground": "inv-18", "value": "200"}]}
    same = {"rows": [dict(apart["rows"][0]),
                     dict(apart["rows"][1], ground="inv-17")]}
    ia = zfl.run(apart)["report"]["ledger"]["brackets"]
    isame = zfl.run(same)["report"]["ledger"]["brackets"]
    print(f"   two lines on two documents : {ia}")
    print(f"   two lines on ONE document  : {isame}")
    assert ia == {"inv-17": [1, 1], "inv-18": [1, 1]}
    assert isame == {"inv-17": [2, 2]}
    print("   That is the whole answer to 'the ground column says nothing'.")
    print("   The name is opaque — the machine never looks inside it — but")
    print("   its IDENTITY is load-bearing: put two lines on one invoice and")
    print("   losing it costs two claims instead of one. Nothing else in the")
    print("   table can say that, and `means` certainly cannot: a gloss is")
    print("   for the reader, a ground is what the arithmetic of collapse")
    print("   runs on.")


def sec4_an_unknown_is_a_question_not_a_gap():
    print("-" * 72)
    print("4. ASKING FOR A NUMBER, WHICH IS WHAT PEOPLE ACTUALLY WANT")
    for claim in ("x - 10 = 20", "x - 10 == 20", "sum(x,x) = 60",
                  "-x + 100 = 70"):
        doc = {"rows": [{"name": "x", "means": "the unknown",
                         "status": "unverified", "value": "?"}],
               "claim": claim}
        r = zfl.run(doc)
        assert r["ok"], r["issues"]
        n = r["report"]["numeric"]
        sv = n["solved"]["x"]
        print(f"   {claim:16} -> {n['disposition']:8} x = {sv['lo']}"
              f"  ({sv['prov']})")
        assert n["disposition"] == "EARNED" and sv["lo"] == "30"
        # the last one carries a UNARY minus, which the arithmetic reader
        # could not parse until the curator asked it to solve an equation
        # that opened with one
        assert sv["pinned"] and sv["prov"] == "earned"
    print("   `x=?` in the table is a QUESTION, not a missing cell, so the")
    print("   solver answers it — and answers with the provenance the value")
    print("   inherited from the derivation. Judging alone would have said")
    print("   'measure x', which is true and useless when the sheet already")
    print("   determines it.")
    print("   And a lone `=` is read as equality wherever the document has")
    print("   quantities. `x - 10 = 20` is what a person writes; making them")
    print("   type `==` would be the machine's convenience charged to them.")



def sec4c_a_number_without_a_value_goes_back_to_the_translator():
    print("-" * 72)
    print("4c. A NAME READ AS A NUMBER NEEDS A VALUE — AND THE REPAIR LOOP HEARS IT")
    # MEASURED 2026-09-24 on the live studio: three questions in prose, the
    # formula translated right every time, the sought x left without a value
    # every time. The validator said nothing, so the repair loop never ran,
    # and the run answered "stray character '*'".
    import json
    import translator
    bad = {"rows": [{"name": "x", "means": "the number sought",
                     "status": "unverified"}],
           "claim": "x*x - 2*x + 5 == 0"}
    got = [(i["code"], i["where"]) for i in zfl.validate(bad)
           if i["level"] == "error"]
    assert got == [("E_NO_VALUE", "row 1 / value")], got
    r = zfl.run(bad)
    assert not r["ok"] and {i["code"] for i in r["issues"]
                            if i["level"] == "error"} == {"E_NO_VALUE"}, r
    fixed = json.loads(json.dumps(bad))
    fixed["rows"][0]["value"] = "?"
    heard, replies = [], [json.dumps(bad), json.dumps(fixed)]

    def model(messages, cfg, temperature=0.2):
        heard.append(messages[-1]["content"])
        return replies[min(len(heard), len(replies)) - 1]      # repeats its last word

    real, translator.llm = translator.llm, model
    try:
        out = translator.fill([{"role": "user", "content":
                                "Is there a number x such that x squared "
                                "minus 2x plus 5 equals zero?"}], "en")
    finally:
        translator.llm = real
    assert len(heard) == 2, heard
    assert "E_NO_VALUE" in heard[1] and "row 1 / value" in heard[1], heard[1]
    assert out["ok"] and out["repaired"], out
    assert out["doc"]["rows"][0]["value"] == "?", out["doc"]
    r = zfl.run(out["doc"])
    assert r["ok"] and r["report"]["numeric"]["disposition"], r
    # A VALID document the run refuses (the same day's live model): the loop
    # must hear the run too, and hear it in words, not as a Python error.
    odd = {"rows": [dict(fixed["rows"][0]),
                    {"name": "eq0", "means": "the equation holds", "status": "unverified"}],
           "claim": "eq0 == (x*x - 2*x + 5 == 0)"}
    assert zfl.validate(odd) == [] or not any(
        i["level"] == "error" for i in zfl.validate(odd)), zfl.validate(odd)
    heard2, replies2 = [], [json.dumps(odd), json.dumps(fixed)]

    def model2(messages, cfg, temperature=0.2):
        heard2.append(messages[-1]["content"])
        return replies2[min(len(heard2), len(replies2)) - 1]      # repeats its last word

    real, translator.llm = translator.llm, model2
    try:
        out2 = translator.fill([{"role": "user", "content": "Is there such an x?"}], "en")
    finally:
        translator.llm = real
    assert len(heard2) == 2 and "E_UNREADABLE" in heard2[1], heard2
    assert "not arithmetic" in heard2[1] and "NoneType" not in heard2[1], heard2[1]
    assert out2["ok"] and out2["repaired"] and zfl.run(out2["doc"])["ok"], out2
    # a POWER written as `^` (XOR): a number where a statement goes goes back
    power = json.loads(json.dumps(fixed))
    power["claim"] = "x^2 - 2*x + 5 == 0"
    got = [(i["code"], i["where"]) for i in zfl.validate(power) if i["level"] == "error"]
    assert got == [("E_NUMBER_AS_STATEMENT", "claim")], got
    heard4, replies4 = [], [json.dumps(power), json.dumps(fixed)]

    def model4(messages, cfg, temperature=0.2):
        heard4.append(messages[-1]["content"])
        return replies4[min(len(heard4), len(replies4)) - 1]      # repeats its last word

    real, translator.llm = translator.llm, model4
    try:
        out4 = translator.fill([{"role": "user", "content": "Is there such an x?"}], "en")
    finally:
        translator.llm = real
    assert len(heard4) == 2 and "E_NUMBER_AS_STATEMENT" in heard4[1] and "x*x" in heard4[1], heard4
    assert out4["ok"] and out4["repaired"] and out4["doc"]["claim"] == fixed["claim"], out4
    # and a document the run reads goes the mirror's way, not the repair's
    heard3, replies3 = [], [json.dumps(fixed), json.dumps(fixed)]

    def model3(messages, cfg, temperature=0.2):
        heard3.append(messages[-1]["content"])
        return replies3[min(len(heard3), len(replies3)) - 1]      # repeats its last word

    real, translator.llm = translator.llm, model3
    try:
        out3 = translator.fill([{"role": "user", "content": "Is there such an x?"}], "en")
    finally:
        translator.llm = real
    assert out3["ok"] and out3.get("mirrored") and not out3["repaired"], out3
    print("   x*x - 2*x + 5 == 0 with x left empty -> E_NO_VALUE at row 1 / value")
    print("   the repair turn carried it to the model; the returned x = ?,")
    print(f"   and the numeric floor answered: {r['report']['numeric']['disposition']}.")
    print("   The rule the translator was already told (a sought number gets ?)")
    print("   is now also what the validator enforces, so a model that forgets")
    print("   it is corrected by the loop instead of by the person.")
    print("   A document the validator passes and the run refuses (propositions")
    print("   compared with ==) goes back too, with the refusal in words; one the")
    print("   run reads still takes the mirror's path.")


def sec4d_a_name_that_multiplies_itself_is_one_number():
    print("-" * 72)
    print("4d. THE CURATOR'S X*X-2X+5=0: REFUTED, AND TWO ROOTS ARE TWO ANSWERS")
    q = {"name": "x", "means": "the number sought", "status": "unverified", "value": "?"}
    r = zfl.run({"rows": [q], "claim": "x*x - 2*x + 5 = 0"})
    n = r["report"]["numeric"]
    assert n["disposition"] == "REFUTED" and not n.get("missing"), n
    n = zfl.run({"rows": [q], "claim": "x*x - 5*x + 6 = 0"})["report"]["numeric"]
    assert n["disposition"] == "EARNED" and n["solved"]["x"]["roots"] == ["2", "3"], n
    n = zfl.run({"rows": [q], "claim": "x*x == 2"})["report"]["numeric"]
    assert n["disposition"] == "EARNED" and n["solved"]["x"]["roots"] == ["-√2", "√2"], n
    assert not any("still a box" in c for c in n["next_check"]), n["next_check"]
    m = {"name": "X", "means": "a measured number", "status": "verified",
         "ground": "doc-1", "value": "[-inf,inf]"}
    n = zfl.run({"rows": [m], "claim": "(X-1)*(X-1) + 4 == 0"})["report"]["numeric"]
    assert n["disposition"] == "REFUTED", n
    print("   x = ?: x*x - 2*x + 5 = 0 -> REFUTED (D = -16), and no 'needs a fact'")
    print("   x*x - 5*x + 6 = 0 -> EARNED, x = 2 or 3; x*x == 2 -> EARNED, x = ±√2 exactly:")
    print("   the root is held as p + q·√d, not only as its 12-digit clamp.")
    plot = {"rows": [dict(q, name="s"), dict(q, name="area")],
            "claim": "(area == s*s) & (area - 2*s + 5 == 0)"}
    n = zfl.run(plot)["report"]["numeric"]
    assert n["disposition"] == "REFUTED" and not n.get("missing"), n
    plot["claim"] = "area == s*s & area - 5*s + 6 == 0"
    n = zfl.run(plot)["report"]["numeric"]
    assert n["solved"]["s"]["roots"] == ["2", "3"] and n["solved"]["area"]["roots"] == ["4", "9"], n
    print("   X measured over the reals: (X-1)*(X-1) + 4 == 0 -> REFUTED.")
    print("   The plot as a system, area == s*s & area - 2*s + 5 == 0 -> REFUTED;")
    print("   with area - 5*s + 6: s = 2 or 3 and area = 4 or 9, never the box [4, 9].")

def sec4e_a_system_whose_coefficients_are_known_within_tolerance():
    print("-" * 72)
    print("4e. A LINEAR SYSTEM WITH UNCERTAIN COEFFICIENTS (matrices, 2026-10-09)")
    import zflexamples as X
    ex = next(e for e in X.EXAMPLES if e["en"] == "a circuit whose parts are known within tolerance")
    n = zfl.run(ex["doc"])["report"]["numeric"]
    I, U = n["solved"]["I"], n["solved"]["U"]
    # independent: series circuit, I = V/(R1+R2), U = V*R2/(R1+R2), extremes at the corners
    assert (I["lo"], I["hi"]) == ("1/33", "1/27"), I
    assert (U["lo"], U["hi"]) == ("180/29", "220/31"), U
    assert I["prov"] == "earned" and sorted(I["from"]) == ["R1", "R2", "V"], I
    assert any("exact at the corners" in l for l in n["log"]), n["log"]
    # stage two (ZTL 62b71ea): the laws hold at every reading by construction
    assert n["disposition"] == "EARNED", n["disposition"]
    # and a measured quantity is not narrowed by the claim it is judged against
    sf = zfl.run({"rows": [{"name": "y", "means": "a measured length", "status": "verified",
                            "ground": "m1", "value": "[1,2]"},
                           {"name": "x", "means": "sought", "status": "unverified", "value": "?"}],
                  "claim": "(y >= 3/2) & (x == 1)"})["report"]["numeric"]
    assert sf["disposition"] == "OPEN", sf
    rk2 = zfl.run({"rows": [{"name": "p", "means": "a part", "status": "verified", "ground": "g",
                             "value": "[1/2,2]"},
                            {"name": "x", "means": "sought", "status": "unverified", "value": "?"},
                            {"name": "y", "means": "sought", "status": "unverified", "value": "?"}],
                   "claim": "(x - p*y == 0) & (p*x + y == 1)"})["report"]["numeric"]
    # since ZTL ca17ad4 one rank-two parameter is SOLVED (it used to be refused, and the old
    # check matched the words "rank > 1", which the new log line also contains): read the range
    assert (rk2["solved"]["x"]["lo"], rk2["solved"]["x"]["hi"]) == ("2/5", "1/2"), rk2["solved"].get("x")
    print("   R1 in [90,110], R2 in [180,220] on 10 V: I in [1/33, 1/27], U in [180/29, 220/31] —")
    print("   exactly the corner hull, earned from the two datasheets and the supply;")
    print("   the report's log says so; a rank-two parameter is solved at its critical point;")
    print("   the laws come back EARNED, and (y >= 3/2) & (x == 1) with y measured in [1,2] is OPEN.")
    # 4f (ZTL 3a296b5): a name DEFINED by a product of toleranced quantities is narrowed — exactly
    # at the corners when multilinear, by the interval reading otherwise; never inside a system
    row = lambda n, v: {"name": n, "means": "a part", "status": "verified", "ground": "datasheet", "value": v}
    ask = lambda n: {"name": n, "means": "sought", "status": "unverified", "value": "?"}
    t = zfl.run({"rows": [row("R", "[99/10,101/10]"), row("C", "[19/2,21/2]"), ask("tau")],
                 "claim": "tau == R*C"})["report"]["numeric"]
    assert (t["solved"]["tau"]["lo"], t["solved"]["tau"]["hi"]) == ("1881/20", "2121/20"), t["solved"]
    assert any("multilinear, exact at the corners" in l for l in t["log"]), t["log"]
    pw = zfl.run({"rows": [row("V", "5"), row("R1", "[99/10,101/10]"), row("R2", "[99/10,101/10]"),
                           ask("I"), ask("U"), ask("P")],
                  "claim": "(V - U == I*R1) & (U == I*R2) & (P == I*I*R1)"})["report"]["numeric"]
    assert (pw["solved"]["P"]["lo"], pw["solved"]["P"]["hi"]) == ("12375/20402", "12625/19602"), pw["solved"]["P"]
    assert any("interval reading" in l for l in pw["log"]), pw["log"]
    print("   4f. x = p/(1+p^2), p in [1/2, 2] (rank two, 4e): [2/5, 1/2], the interior peak at p = 1;")
    print("   4f. tau == R*C with R, C boxed: [1881/20, 2121/20], exact at the corners;")
    print("       P == I*I*R1 after the system bounds I: [12375/20402, 12625/19602], an interval reading.")


def sec13_naive_sets_are_in_the_language():
    print("-" * 72)
    print("13. NAIVE SETS IN THE LANGUAGE (2026-11-05): cells become rows, the passport reads them")
    import time
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "ztlcore"))
    import znaive
    russell = {"rows": [], "sets": {"a": {"list": []}, "b": {"list": ["b"]},
                                    "R": {"abs": ["not", ["in", "x", "x"]]}}}
    r = zfl.run(dict(russell, claim="in(a, R) & ~in(b, R)"))
    assert r["ok"] and r["report"]["judge"]["disposition"] == "EARNED", r
    assert [(p["component"], p["kind"]) for p in r["report"]["passport"]] == [(["R_in_R"], "PARADOX")], r
    r = zfl.run(dict(russell, claim="R_in_R"))
    assert r["ok"] and r["report"]["judge"]["disposition"] == "OPEN", r["report"]["judge"]
    # the same verdicts as the kernel's own naive judge, on every cell of its four universes
    for name, ex in znaive.EXAMPLES.items():
        nv = znaive.check(ex)
        for st in nv["sets"]:
            for m in st["in"] + st["out"] + [q["member"] for q in st["quarantined"]]:
                cl = f"{m}_in_{st['set']}"
                rz = zfl.run({"rows": [], "sets": ex, "claim": cl})
                assert rz["ok"], (name, cl, rz["issues"])
                v = rz["report"]["judge"]["verdict"]
                want = "T" if m in st["in"] else "F" if m in st["out"] else "Z"
                assert v == want, (name, cl, v, want)
                if want == "Z":
                    kinds = {c: p["kind"] for p in rz["report"]["passport"] for c in p["component"]}
                    want_kind = next(q["passport"] for q in st["quarantined"] if q["member"] == m)
                    # an INPUT cell no definition reads is, in ZFL, simply an unverified row (no system to join)
                    plain_input = (want_kind == "INPUT" and cl not in kinds and any(
                        r_["name"] == cl and r_["status"] == "unverified" for r_ in zfl.coerce(
                            {"rows": [], "sets": ex, "claim": cl})["rows"]))
                    assert plain_input or kinds.get(cl) == want_kind or want_kind == "DOWNSTREAM", \
                        (name, cl, kinds.get(cl), want_kind)
    # the door: refusals are issues on `sets`, at once; coerce twice adds nothing twice
    deep = ["in", "x", "x"]
    for v in "abcdef":
        deep = ["all", v, ["or", ["in", v, "x"], deep]]
    t0 = time.time()
    for bad in ({"T": {"list": []}}, {"A": {"abs": ["in", "x", "ghost"]}}, "{not json",
                {f"s{i}": {"abs": deep} for i in range(8)}, {"abs": {"list": []}}):
        r = zfl.run({"rows": [], "sets": bad, "claim": "p"})
        assert not r["ok"] and "E_SETS" in [i["code"] for i in r["issues"]], (bad, r["issues"])
    assert time.time() - t0 < 2
    r = zfl.run({"rows": [{"name": "A_in_A", "means": "m", "status": "unverified"}],
                 "sets": {"A": {"list": []}}, "claim": "A_in_A"})
    assert not r["ok"] and "E_SETS" in [i["code"] for i in r["issues"]]
    d = zfl.coerce(dict(russell, claim="R_in_R"))
    assert len(zfl.coerce(d)["rows"]) == len(d["rows"]) == 3, d["rows"]
    # a person's own defined row may lean on a cell
    r = zfl.run({"rows": [{"name": "ok", "means": "a is in R and paid", "status": "defined",
                           "ground": "in(a, R) & paid"},
                          {"name": "paid", "means": "paid", "status": "verified", "ground": "inv-1"}],
                 "sets": russell["sets"], "claim": "ok"})
    assert r["ok"] and r["report"]["judge"]["verdict"] == "T", r
    print("   Russell's set: a ∈ R and b ∉ R EARNED, R ∈ R a PARADOX through the same passport as the Liar;")
    print("   every cell of znaive's four example universes reads the same in ZFL (T/F/Z and the passport);")
    print("   bad names, unknown names, broken JSON, an oversized universe, a name clash: E_SETS, at once.")

def sec14_the_model_chain_moves_on():
    print("-" * 72)
    print("14. THE MODEL CHAIN (2026-11-05): Groq first, every model in turn, a limit moves on at once")
    import providers
    import translator
    calls, real = [], providers.chat
    have = {"groq", "nvidia"}
    real_avail = providers.available
    providers.available = lambda: [{"provider": p, "has_key": p in have} for p in providers.PROVIDERS]

    def fake(script):
        def chat(messages, provider, model="", key="", temperature=0.2, wait_on_limit=True):
            calls.append((provider, model, wait_on_limit))
            outcome = script.get((provider, model), "ok")
            if outcome != "ok":
                raise providers.ProviderError(outcome)
            return f"answer from {provider}/{model}"
        return chat
    try:
        g = providers.MODELS["groq"]
        providers.chat = fake({("groq", g[0]): "HTTP 429: rate limit"})
        out = translator.llm([{"role": "user", "content": "q"}], {})
        assert out == f"answer from groq/{g[1]}" and calls == [("groq", g[0], False), ("groq", g[1], False)], calls
        calls.clear()
        providers.chat = fake({("groq", m): "HTTP 429: rate limit" for m in g})
        out = translator.llm([{"role": "user", "content": "q"}], {})
        assert out.startswith("answer from nvidia/") and [c[0] for c in calls] == ["groq"] * len(g) + ["nvidia"], calls
        assert all(c[2] is False for c in calls), "no attempt before the last may sleep on a limit"
        calls.clear()
        chain = translator._chain({})
        providers.chat = fake({k: "HTTP 429" for k in chain[:-1]})
        translator.llm([{"role": "user", "content": "q"}], {})
        assert len(calls) == len(chain) and calls[-1][2] is True, "the LAST attempt may wait on a limit"
        calls.clear()
        providers.chat = fake({k: "HTTP 410: Gone" for k in translator._chain({})})
        try:
            translator.llm([{"role": "user", "content": "q"}], {})
            raise AssertionError("all failed, yet an answer")
        except translator.TranslatorError as e:
            assert all(m in str(e) for m in g), str(e)          # every refusal named, not the last
        calls.clear()
        providers.chat = fake({("groq", g[0]): "HTTP 429"})
        try:
            translator.llm([{"role": "user", "content": "q"}], {"provider": "groq", "model": g[0]})
            raise AssertionError("a person's chosen model was replaced")
        except translator.TranslatorError:
            pass
        assert calls == [("groq", g[0], True)], calls
    finally:
        providers.chat, providers.available = real, real_avail
    print(f"   groq {g[0]} at its limit -> {g[1]} at once (no sleeping); all Groq at the limit -> NVIDIA;")
    print("   every model refusing -> a refusal naming each; a person's chosen model is never replaced.")

def sec15_a_convention_changes_the_order_never_the_verdict():
    """(2026-11-05) The `convention` column. Both sides: on a battery of documents the numeric disposition and polarity
    are the same with and without it, and the cures differ only measure <-> stipulate for that row; an empirical row
    beside it keeps 'measure'; a convention with 'sample' or without a value is refused (E_CONVENTION). Sabotage: a
    to_sheet that drops the token must break the cure check."""
    import copy
    print("-" * 72)
    print("§15 a convention changes the order, never the verdict")
    docs = [
        ({"rows": [{"name": "P", "status": "verified", "ground": "methods", "value": "[1/4,1/2]"}]}, "P == 1/2"),
        ({"rows": [{"name": "P", "status": "verified", "ground": "methods", "value": "[1/4,1/2]"}]}, "P >= 1/4"),
        ({"rows": [{"name": "P", "status": "unverified", "value": "[1/4,1/2]"}]}, "P > 1/2"),
        ({"rows": [{"name": "P", "status": "verified", "ground": "methods", "value": "[1/4,1/2]"},
                   {"name": "n", "status": "verified", "ground": "count", "value": "[30,50]"}]}, "P * n >= 10"),
    ]
    for doc, claim in docs:
        plain = copy.deepcopy(doc); plain["claim"] = claim
        conv = copy.deepcopy(plain); conv["rows"][0]["convention"] = True
        a, b = zfl.run(plain)["report"]["numeric"], zfl.run(conv)["report"]["numeric"]
        assert (a["disposition"], a.get("polarity")) == (b["disposition"], b.get("polarity")), (claim, a, b)
        assert [c.replace("measure P", "stipulate P") for c in a["next_check"]] == b["next_check"], (claim, a, b)
    both = {"rows": [{"name": "P", "status": "verified", "ground": "methods", "value": "[1/4,1/2]", "convention": True},
                     {"name": "n", "status": "verified", "ground": "count", "value": "[30,50]"}], "claim": "P * n >= 10"}
    cures = zfl.run(both)["report"]["numeric"]["next_check"]
    assert "stipulate P" in cures and "measure n" in cures, cures
    for bad in ({"rows": [{"name": "P", "status": "unverified", "value": "[0,1]", "convention": True, "sample": True}],
                 "claim": "P > 0"},
                {"rows": [{"name": "q", "status": "unverified", "convention": True}], "claim": "q"}):
        assert any(i["code"] == "E_CONVENTION" for i in zfl.validate(bad)), bad
    real = zfl.to_sheet
    zfl.to_sheet = lambda rows: real(rows).replace(" convention", "")         # sabotage: the token never travels
    try:
        assert "stipulate P" not in zfl.run(both)["report"]["numeric"]["next_check"]
    finally:
        zfl.to_sheet = real
    print("   same verdict with and without the column; 'stipulate' for the convention, 'measure' beside it;")
    print("   convention + separate measurements, or a convention with no value: E_CONVENTION; sabotage caught")


def sec16_a_lone_equals_is_read_by_the_types_of_its_sides():
    """(2026-11-05) `=` between numbers is numeric equality, between statements the biconditional, a statement against
    a number is refused (E_TYPE_EQ) — whatever else the document holds. Both sides: the equations of the catalogue
    read as before; `p = q` and `p = (x > 1)` are biconditionals even beside a quantity. Sabotage: the old
    per-document reading must fail the new cases."""
    print("-" * 72)
    print("§16 a lone '=' is read by the types of its sides")
    rows = [{"name": "p", "status": "unverified", "means": "a"}, {"name": "q", "status": "unverified", "means": "b"},
            {"name": "x", "status": "verified", "ground": "m", "value": "2", "means": "c"}]
    want = {"p = q": "p = q", "p = (x > 1)": "p = (x > 1)", "(x > 1) = p": "(x > 1) = p",
            "x = 2": "x == 2", "x - 1 = 1 & p": "x - 1 == 1 & p", "x * 3 = 6": "x * 3 == 6",
            "sum(x,x) = 4": "sum(x,x) == 4", "p = q & (x >= 1)": "p = q & (x >= 1)"}
    for c, n in want.items():
        assert zfl.normalise(c, rows) == n, (c, zfl.normalise(c, rows))
        assert zfl.run({"rows": rows, "claim": c})["ok"], c
    for c in ("p = x", "p = 5"):
        assert any(i["code"] == "E_TYPE_EQ" for i in zfl.validate({"rows": rows, "claim": c})), c
    # without any quantity a lone `=` between statements is the biconditional, as it always was
    assert zfl.normalise("p = q", rows[:2]) == "p = q"
    # verdicts: p = (x > 1) with x = 2 is p's own status; p = q over two Z rows is open
    r = zfl.run({"rows": rows, "claim": "p = (x > 1)"})["report"]
    assert r["numeric"]["disposition"] == "OPEN", r
    real = zfl.eq_kinds
    zfl.eq_kinds = lambda text, rows: [(m.start(), "unknown") for m in zfl._LONE_EQ.finditer(text)]   # sabotage
    try:
        assert zfl.normalise("p = q", rows) == "p == q"          # the old reading comes back ...
        assert not zfl.run({"rows": rows, "claim": "p = q"})["ok"]  # ... and the biconditional dies again
    finally:
        zfl.eq_kinds = real
    # whitespace inside a value is layout: "[0, 1]" reads as "[0,1]" (a blind formalization died three rounds on it)
    for v in ("[0, 1]", " [0 ,1] ", "[ 1/4 , 1/2 ]"):
        assert zfl.run({"rows": [{"name": "w", "status": "unverified", "value": v, "means": "m"}],
                        "claim": "w >= 0"})["ok"], v
    print("   numbers = numbers -> ==; statements = statements -> the biconditional, beside a quantity too;")
    print("   a statement = a number -> E_TYPE_EQ; the old per-document reading, as sabotage, is caught")


def sec17_a_clock_beside_a_numeric_claim_never_crashes():
    """(2026-11-05) A row with a clock (expires_on) and a claim that compares numbers made the time layer raise
    ("stray character '>'") on a document that had passed validation — a public service turning a question into an
    internal error. Now the time layer reads statements only and says so (W_EPOCH_NUMERIC); a statement claim beside
    a clock still gets the time layer. Both sides."""
    print("-" * 72)
    print("§17 a clock beside a numeric claim never crashes, and says what it did not read")
    rows = [{"name": "cert", "means": "a certificate", "status": "verified", "ground": "story", "ground_kind": "certificate",
             "expires_on": "cert_end"},
            {"name": "cert_end", "means": "the end", "status": "unverified"},
            {"name": "fee", "means": "fee", "status": "unverified", "value": "?"},
            {"name": "paid", "means": "paid", "status": "unverified", "value": "?"},
            {"name": "ok", "means": "covered", "status": "unverified"}]
    for c in ("paid >= fee", "paid >= fee & ok = (paid >= fee)"):
        r = zfl.run({"rows": rows, "claim": c})
        assert r["ok"] and "epoch" not in r["report"], (c, r.get("issues"))
        assert any(i["code"] == "W_EPOCH_NUMERIC" for i in r["issues"]), c
    for c in ("cert & ok", "cert -> ok"):
        r = zfl.run({"rows": rows, "claim": c})
        assert r["ok"] and "epoch" in r["report"], c
        assert not any(i["code"] == "W_EPOCH_NUMERIC" for i in r["issues"]), c
    print("   numeric claim + clock: no crash, the time layer named as not reading it; statements: the time layer reads")


def sec4b_every_example_runs_and_json_types_are_taken_as_they_come():
    print("-" * 72)
    print("4b. THE CATALOGUE, AND WHAT ARRIVES FROM A MODEL")
    import zflexamples as X
    kinds = {}
    for e in X.EXAMPLES:
        r = zfl.run(e["doc"])
        assert r["ok"], (e["en"], r["issues"])
        kinds.setdefault(e["kind"], 0)
        kinds[e["kind"]] += 1
    print(f"   {len(X.EXAMPLES)} examples, all validating and running: {kinds}")
    # THE PUBLISHED PROMISE. §7 of the paradox docket (v1.1, DOI
    # 10.5281/zenodo.21916017) tells the reader the studio holds this
    # paper's entire collection and names the cases. A studio missing one
    # of them does not have a gap — it makes an issued paper false. So the
    # list is checked here, by the names the v1 studio used, which are the
    # names the paper quotes.
    import ztlstudio
    promised = {e["name"] for e in ztlstudio.EXAMPLES}
    present = {e.get("paper") for e in X.EXAMPLES if e.get("paper")}
    print(f"   cases the docket promises: {len(promised)}, present: "
          f"{len(present & promised)}")
    assert promised <= present, sorted(promised - present)
    assert set(kinds) == set(X.KINDS)
    print("   An example is a promise about the machine, so a broken one may")
    print("   not ship. This caught a real crash on the first run: a row with")
    print("   value `?` was being turned into the ledger claim `b == ?`,")
    print("   which the sheet parser rightly refused — a question is not a")
    print("   claim about a value.")
    # a model writes JSON, and JSON has JSON's types
    doc = {"rows": [{"name": "a", "means": "x", "status": "verified",
                     "ground": "inv-1", "value": 3000, "unit": "RUB"},
                    {"name": "cap", "means": "y", "status": "verified",
                     "ground": "c", "value": 5000, "unit": "RUB"}],
           "claim": "a <= cap"}
    r = zfl.run(doc)
    print(f"   values arriving as NUMBERS: {r['report']['numeric']['sheet']}")
    assert r["ok"] and r["report"]["numeric"]["disposition"] == "EARNED"
    print("   `\"value\": 3000` is not wrong of a model or of a caller, and it")
    print("   crashed the validator the first time the AI filled the table.")
    print("   Types are coerced once at the door instead of defensively in")
    print("   twenty places.")


def sec5_the_spec_can_build_the_form_and_the_page():
    print("-" * 72)
    print("5. ONE SPEC BEHIND THE FORM, THE VALIDATOR AND THE PAGE")
    for lang in ("en", "ru"):
        spec = zfl.form_spec(lang)
        cols = spec["columns"]
        assert len(cols) == len(zfl.COLUMNS)
        assert all(c["label"] and c["help"] for c in cols)
        widgets = sorted({c["widget"] for c in cols})
        print(f"   {lang}: {len(cols)} columns, widgets {widgets}")
        for c in cols:
            if c["widget"] in ("choice", "multi"):
                assert c["options"] and all(o["label"] for o in c["options"])
    req = [c["key"] for c in zfl.form_spec()["columns"] if c["required"]]
    cond = [c["key"] for c in zfl.form_spec()["columns"]
            if c["required_when"]]
    print(f"   always required: {req}   required in context: {cond}")
    assert req == ["name", "status"] and cond == ["ground"]
    print("   The widget follows from the column's TYPE, so a dropdown, a")
    print("   toggle and a stepper are not decisions the front-end makes —")
    print("   they are read off the same table that the validator enforces")
    print("   and the reference page will describe. Add a column here and")
    print("   it appears in all three, or in none of them.")




def sec7_the_ground_gate_demotes_phantom_words():
    """Ворота оснований (2026-08-27). Три инварианта, каждый — прогон:
    без реестра поведение прежнее; слово-фантом при реестре НЕ зарабатывает
    и падает в кредит, поимённо; настоящее основание из реестра стоит."""
    print("\n### 7. The ground gate: a phantom word must not earn")
    doc = {"rows": [
        {"name": "p", "means": "x", "status": "verified",
         "ground": "СЛОВО-ФАНТОМ"},
        {"name": "q", "means": "y", "status": "verified", "ground": "inv-17"}],
        "claim": "p & q"}
    a = zfl.run(doc)
    ja = a["report"]["judge"]
    assert (ja["verdict"], ja["grade"]) == ("T", "hereditary")
    assert "demoted_grounds" not in a["report"]          # без реестра — как раньше
    b = zfl.run(doc, ground_registry={"inv-17"})
    jb = b["report"]["judge"]
    assert jb["verdict"] == "F" and jb["disposition"] == "OPEN"
    assert b["report"]["demoted_grounds"] == ["p"]       # поимённо
    c = zfl.run({"rows": [doc["rows"][1]], "claim": "q"},
                 ground_registry={"inv-17"})
    jc = c["report"]["judge"]
    assert (jc["verdict"], jc["grade"]) == ("T", "hereditary")
    print("   without a registry: byte-identical behaviour;")
    print("   with one: the phantom is demoted BY NAME and the verdict")
    print("   honestly falls OPEN; a registered ground still earns.")

def sec7b_the_receipt_tells_what_was_said_from_what_was_done():
    """The tier travels into the receipt (2026-09-24). Until then run() issued
    its receipt BEFORE computing the stipulation tag, and hashed a tiered
    registry by its names alone — so the same table under "log:story" and
    under "log:act" gave receipts equal to the byte."""
    import warrant_receipt as wr
    print("\n### 7b. The receipt tells what was said from what was done")
    doc = {"rows": [
        {"name": "done", "means": "the agent's own log says it did it",
         "status": "verified", "ground": "log"},
        {"name": "ok", "means": "the grant verifies", "status": "verified",
         "ground": "grant"}],
        "claim": "done & ok"}
    said_reg, acted_reg = {"log": "story", "grant": "place"}, {"log": "act", "grant": "place"}
    said, acted = zfl.run(doc, ground_registry=said_reg), zfl.run(doc, ground_registry=acted_reg)
    rs, ra = said["report"]["receipt"], acted["report"]["receipt"]
    assert [x["name"] for x in said["report"]["on_stipulation"]] == ["done"]
    assert rs["on_stipulation"] == ["done"], rs["on_stipulation"]
    assert ra["on_stipulation"] is None
    assert rs["registry"]["digest"] != ra["registry"]["digest"]
    assert rs["digest"] != ra["digest"]
    assert wr.verify(rs) and wr.verify(ra)
    # the receipt run() issues is the one anybody issues from its report
    assert rs == wr.receipt(said, doc, "", ground_registry=said_reg)
    # a plain set carries no tiers and hashes exactly as before
    flat = zfl.run(doc, ground_registry={"log", "grant"})["report"]["receipt"]
    assert flat["registry"]["digest"] == wr._sha(wr._canon(["grant", "log"]))
    assert flat["on_stipulation"] is None
    print("   story and act give different receipts; the tag is in the one")
    print("   run() issues, equal to a receipt issued from outside; a registry")
    print("   without tiers hashes as it always did.")

def sec7c_number_claims_carry_their_verdict_and_the_root_is_read():
    """Two organs that were built and not reached (2026-09-24): the receipt
    of a number claim carried no verdict at all, and `sqrt` — in the core
    since 2026-09-21 — was refused by the language as an undeclared row."""
    print("\n### 7c. A number claim's receipt carries its verdict; the root is read")
    sheet = {"claim": "paid <= fee", "rows": [
        {"name": "fee", "means": "the fee", "status": "verified", "ground": "inv-1", "value": "100"},
        {"name": "paid", "means": "what was paid", "status": "verified", "ground": "bank-2", "value": "80"}]}
    v = zfl.run(sheet)["report"]["receipt"]["verdict"]
    assert (v["value"], v["disposition"], v["grade"]) == ("T", "EARNED", "hereditary"), v
    credit = {"claim": "paid <= fee", "rows": [
        {"name": "fee", "means": "the fee", "status": "verified", "ground": "inv-1", "value": "100"},
        {"name": "paid", "means": "not documented", "status": "unverified", "value": "120"}]}
    v = zfl.run(credit)["report"]["receipt"]["verdict"]
    assert (v["value"], v["disposition"], v.get("polarity")) == ("F", "ON CREDIT", "toward F"), v
    root = {"claim": "sqrt(a) > 1.41", "rows": [
        {"name": "a", "means": "the side", "status": "verified", "ground": "m1", "value": "2"}]}
    r = zfl.run(root)
    assert r["ok"] and r["report"]["numeric"]["disposition"] == "EARNED", r
    r = zfl.run(dict(root, claim="sqrt(a) > 1.42"))
    assert r["report"]["numeric"]["disposition"] == "REFUTED", r
    print("   a number claim's receipt says T/F, its disposition and grade, and on")
    print("   credit its side; sqrt(a) > 1.41 is read, EARNED, and > 1.42 REFUTED.")

def sec8_the_credit_that_cannot_be_redeemed():
    """The judge and the passport stop contradicting each other.

    Found 2026-08-28 marking up Protagoras v. Euathlus: one report said
    `until-verification` ("go and check") about the very name the passport
    called a PERMANENT refusal ("there is nothing to check, ever"). Three
    invariants here — the mark appears where the ring is dead, it does NOT
    appear on an ordinary unverified atom, and the verdict itself is
    untouched (the core computed it correctly; only what the marking could
    not say is added beside it)."""
    print("\n### 8. a credit that cannot be redeemed says so")

    liar = {"claim": "L", "rows": [
        {"name": "L", "means": "this sentence is false",
         "status": "defined", "ground": "~Tr(L)"}]}
    j = zfl.run(liar)["report"]["judge"]
    assert j["credit"] == "UNREDEEMABLE", j
    assert j["unredeemable"] == ["L"], j
    assert j["grade"] == "until-verification", j      # the grade is NOT rewritten
    assert j["verdict"] == "Z", j                     # nor the verdict
    print("   the liar: grade untouched, credit marked UNREDEEMABLE")

    # An ordinary unverified atom is a real credit — it must NOT be marked.
    plain = {"claim": "p", "rows": [
        {"name": "p", "means": "the cat lives next door",
         "status": "unverified", "ground": ""}]}
    j2 = zfl.run(plain)["report"]["judge"]
    assert "credit" not in j2, j2
    print("   an ordinary mark is left alone — no false positive")

    # A grounded definition is completable: no mark either.
    grounded = {"claim": "g", "rows": [
        {"name": "seen", "means": "checked", "status": "verified",
         "ground": "logbook"},
        {"name": "g", "means": "g is what was seen",
         "status": "defined", "ground": "Tr(seen)"}]}
    j3 = zfl.run(grounded)["report"].get("judge") or {}
    assert "credit" not in j3, j3
    print("   a grounded definition is completable — no mark")


def sec9_the_world_has_a_clock_too():
    """The epoch floor: a conclusion resting on a clocked ground loses it.

    Every other column speaks of what is KNOWN; `expires_on` speaks of what
    stops being true. ZTL has carried the distinction since E25 and proves
    it in `EpochBoundary.lean`, but the table could not say it, so a
    temporal case had to be staged by hand in Python (Protagoras v.
    Euathlus, 2026-08-28). Three invariants: the crossing is computed, it
    is computed THROUGH the definitions, and a document with no clock is
    left exactly as it was."""
    print("\n### 9. the world has a clock, and the table can say so")

    car = {"claim": "deal_ok", "rows": [
        {"name": "registry_recheck", "means": "the pledge registry is re-read",
         "status": "unverified", "ground": ""},
        {"name": "pledge_free", "means": "not pledged", "status": "verified",
         "ground": "registry_extract", "expires_on": "registry_recheck"},
        {"name": "papers_ok", "means": "papers in order", "status": "verified",
         "ground": "vehicle_title"},
        {"name": "deal_ok", "means": "the deal may close", "status": "defined",
         "ground": "Tr(pledge_free) & Tr(papers_ok)"}]}
    e = zfl.run(car)["report"]["epoch"][0]
    assert e["event"] == "registry_recheck" and e["expires"] == ["pledge_free"]
    assert e["before"] == {"verdict": "T", "grade": "hereditary"}, e
    assert e["after"]["verdict"] == "Z", e
    assert e["survives"] is False, e
    print("   the purchased car: T/hereditary before, Z after — did NOT survive")

    # THROUGH the definitions: `deal_ok` is a defined row, and reading the
    # marking alone would have shown Z on both sides and called it survival.
    assert e["before"]["verdict"] != e["after"]["verdict"]
    print("   and it is read through the definition, not around it")

    # An event nobody declared cannot be staged.
    bad = {"claim": "a", "rows": [
        {"name": "a", "means": "x", "status": "verified", "ground": "doc",
         "expires_on": "nowhere"}]}
    codes = {i["code"] for i in zfl.run(bad)["issues"]}
    assert "E_UNKNOWN_NAME" in codes, codes
    # Only ground can expire — a mark has nothing for the clock to take.
    bad2 = {"claim": "a", "rows": [
        {"name": "ev", "means": "e", "status": "unverified", "ground": ""},
        {"name": "a", "means": "x", "status": "unverified", "ground": "",
         "expires_on": "ev"}]}
    codes2 = {i["code"] for i in zfl.run(bad2)["issues"]}
    assert "E_EXPIRY_NO_GROUND" in codes2, codes2
    print("   an undeclared event and an expiring mark are both refused")

    # A document with no clock is untouched: no floor, no key.
    plain = {"claim": "a", "rows": [
        {"name": "a", "means": "x", "status": "verified", "ground": "doc"}]}
    r = zfl.run(plain)
    assert r["applies"]["epoch"] is False and "epoch" not in r["report"]
    print("   a document with no clock is left exactly as it was")


def sec10_what_the_ground_holds_and_what_to_check():
    """After the verdict, the report says what each ground holds and how it
    came out, and — for a claim still resting on unverified inputs — which
    of them to check, by GUARANTEE and by POSSIBILITY (2026-09-24)."""
    print("\n### 10. What the ground holds, and what to check")
    yablo = {"rows": [
        {"name": "s0", "means": "none after is true", "status": "defined", "ground": "~Tr(s1) & ~Tr(s2)"},
        {"name": "s1", "means": "none after is true", "status": "defined", "ground": "~Tr(s2)"},
        {"name": "s2", "means": "none after is true", "status": "verified", "ground": "story"}]}
    rows = zfl.run(yablo)["report"]["passport_rows"]
    assert {n: (v["kind"], v["value"]) for n, v in rows.items()} == {
        "s0": ("GROUNDED", "F"), "s1": ("GROUNDED", "F"), "s2": ("GROUNDED", "T")}, rows
    assert rows["s0"]["reads"] == ["s1", "s2"] and rows["s2"]["reads"] == [], rows
    liar = {"rows": [{"name": "L", "means": "this is false", "status": "defined", "ground": "~Tr(L)"}]}
    assert zfl.run(liar)["report"]["passport_rows"]["L"] == {"kind": "PARADOX", "value": "Z", "reads": ["L"]}

    def unverified(claim, *names):
        return {"claim": claim, "rows": [{"name": n, "means": n, "status": "unverified"} for n in names]}
    rep = zfl.run(unverified("p | ~p", "p"))["report"]
    w = rep["what_to_check"]
    assert w["EARNED"]["guaranteed"] == [["p"]], w
    assert w["REFUTED"]["no_possible_set"] is True, w
    assert rep["judge"]["why"], rep["judge"]
    w = zfl.run(unverified("p & (q | r)", "p", "q", "r"))["report"]["what_to_check"]
    assert w["EARNED"]["possible"] == [["p", "q"], ["p", "r"]] and w["EARNED"]["no_guaranteed_set"], w
    w = zfl.run(unverified("a & b & c & d & e & f & g", *"abcdefg"))["report"]["what_to_check"]
    # read-once (ZTL 610984c): no cap — the one set that settles it is all seven
    assert w["SETTLED"]["guaranteed"] == [list("abcdefg")], w
    assert w["EARNED"]["no_guaranteed_set"] and w["EARNED"]["possible"] == [list("abcdefg")], w
    w = zfl.run(unverified("(a & b) | (a & c) | (d & e)", *"abcde"))["report"]["what_to_check"]
    assert "refused" not in w and w["SETTLED"]["guaranteed"], w     # a repeats: worlds (ZTL 6df2b38)
    many = " & ".join(f"(r{i} | r{i})" for i in range(8))           # eight repeated inputs
    w = zfl.run(unverified(many, *[f"r{i}" for i in range(8)]))["report"]["what_to_check"]
    assert "refused" in w and "up to 3" in w["refused"], w          # past REPEAT_CAP the cap stands
    settle = {"claim": "signed & delivered", "rows": [
        {"name": "signed", "means": "signed", "status": "verified", "ground": "scan-12"},
        {"name": "delivered", "means": "arrived", "status": "unverified"}]}
    w = zfl.run(settle)["report"]["what_to_check"]
    assert w["SETTLED"]["guaranteed"] == [["delivered"]], w      # one check closes it, either way
    assert w["EARNED"]["no_guaranteed_set"] and w["EARNED"]["possible"] == [["delivered"]], w
    done = {"claim": "p", "rows": [{"name": "p", "means": "p", "status": "verified", "ground": "doc"}]}
    assert "what_to_check" not in zfl.run(done)["report"]
    print("   every defined row reports its kind, value and what it reads;")
    print("   a claim on unverified inputs reports what to check, by guarantee")
    print("   and by possibility, says so when no set will do; read-once claims have")
    print("   no cap (seven inputs answered), repeated inputs too up to six of them.")


def sec11_a_public_service_cannot_be_made_to_raise_or_to_stall():
    """Found by probing the public API (2026-09-24): a value past float range
    made run() raise from the ledger branch (the service answered 500), and a
    long product chain took seconds, the readers being quadratic in length."""
    import time
    print("\n### 11. A public service cannot be made to raise or to stall")
    big = {"claim": "*".join(["a"] * 200) + " > b", "rows": [
        {"name": "a", "means": "a", "status": "verified", "ground": "doc", "value": "1" + "0" * 1000},
        {"name": "b", "means": "b", "status": "verified", "ground": "doc", "value": "1"}]}
    r = zfl.run(big)                       # raised OverflowError until this date
    assert r["ok"] is False and any(i["code"] == "E_UNREADABLE" for i in r["issues"]), r
    rows = [{"name": "a", "means": "a", "status": "verified", "ground": "doc", "value": "2"},
            {"name": "b", "means": "b", "status": "verified", "ground": "doc", "value": "1"}]
    long_claim = "*".join(["a"] * 2500) + " > b"
    codes = [(i["code"], i["where"]) for i in zfl.run({"claim": long_claim, "rows": rows})["issues"]]
    assert ("E_TOOLONG", "claim") in codes, codes
    long_ground = [{"name": "s", "means": "s", "status": "defined", "ground": " & ".join(["~Tr(s)"] * 800)}]
    codes = [(i["code"], i["where"]) for i in zfl.run({"rows": long_ground})["issues"]]
    assert ("E_TOOLONG", "row 1") in codes, codes
    near = "*".join(["a"] * 995) + " > b"             # just under the cap (2000 since 2026-09-27)
    t0 = time.time()
    r = zfl.run({"claim": near, "rows": rows})
    assert "E_TOOLONG" not in [i["code"] for i in r.get("issues", [])] and time.time() - t0 < 2.0, r
    # the same claim with `a` left WITHOUT a value: the value check parses the
    # claim once more before refusing it. MEASURED 2026-09-24: the refusal
    # went from 0.25 s to 0.50 s under load 16; a valid claim pays nothing.
    t0 = time.time()
    r = zfl.run({"claim": near, "rows": [dict(rows[0], value=""), rows[1]]})
    assert r["ok"] is False and time.time() - t0 < 2.0, (time.time() - t0, r["issues"])
    print("   a value past float range is an issue, not a traceback; a formula")
    print("   over 2000 characters is refused by name; one under it reads fast.")



def sec12_a_bound_over_the_whole_box_by_certificate():
    """The kernel checks, the studio searches (2026-10-09: ZTL's kernel takes no budget).
    The power into a load peaks INSIDE its range; corners and interval readings miss it."""
    print("\n12. A BOUND OVER THE WHOLE BOX, BY CERTIFICATE")
    import time
    import zflcert
    R = lambda n, v: {"name": n, "value": v, "status": "unverified", "means": n}
    rows = [R("V", "5"), R("Rs", "[10.89,11.11]"), R("RL", "[1,100]"), R("I", "?"), R("VL", "?")]
    laws = ["V - VL = I*Rs", "VL = I*RL"]

    def cert(*cs):
        r = zfl.run({"rows": rows, "claim": "", "bounds": list(cs)})
        assert r["ok"], r["issues"]
        return r["report"]["bounds"]

    c = cert({"bound": "VL*I <= 0.6", "laws": laws})[0]
    assert c["verdict"] == "CHECKED" and "solved the linear laws itself" in c["checked_by"], c
    print(f"   VL*I <= 0.6 (the peak 0.5739 is inside): CHECKED, {c['pieces']} pieces, {c['found_by']}")
    c = cert({"bound": "VL*I <= 0.57", "laws": laws})[0]
    assert c["verdict"] == "FAILS" and zflcert.Fraction(c["value_there"]) > zflcert.Fraction(57, 100), c
    print(f"   VL*I <= 0.57: FAILS at {c['at']} — {c['value_there']} exactly")
    c = cert({"bound": "V*V*RL/((Rs + RL)*(Rs + RL)) <= 0.6"})[0]
    tree = c.get("tree") or zflcert._search(*_expr_for("V*V*RL/((Rs + RL)*(Rs + RL))", rows), "<=",
                                            zflcert.Fraction(3, 5), [0])["tree"]
    c = cert({"bound": "V*V*RL/((Rs + RL)*(Rs + RL)) <= 0.6", "tree": tree})[0]
    assert c["verdict"] == "CHECKED" and c["found_by"] == "brought with the document", c
    bad = {"leaf": "monotone", "signs": {"RL": "+", "Rs": "-"}}
    c = cert({"bound": "V*V*RL/((Rs + RL)*(Rs + RL)) <= 0.6", "tree": bad})[0]
    assert c["verdict"] == "REFUSED" and "kernel rejected" in c["reason"], c
    print("   a brought tree: CHECKED as brought; a false one (RL increasing everywhere): REFUSED by the kernel")
    rows2 = [R("V", "5"), R("Rs", "10/3"), R("RL", "[1,100]")]
    r = zfl.run({"rows": rows2, "claim": "", "bounds": {"bound": "V*V*RL/((Rs + RL)*(Rs + RL)) <= 15/8"}})
    c = r["report"]["bounds"][0]
    assert c["verdict"] == "NOT FOUND" and "nothing is claimed" in c["reason"], c
    print("   the bound exactly AT the peak (15/8 at RL = 10/3): NOT FOUND — nothing claimed either way")
    for junk, word in (({"bound": "VL*I < 0.6"}, "REFUSED"), ({"bound": "VL*I <= x"}, "REFUSED"),
                       ({"bound": "VL*I <= 0.6"}, "REFUSED"),
                       ({"bound": "VL*I <= 0.6", "laws": ["V - VL = I*Rs"]}, "REFUSED"),
                       ({"bound": "VL*I <= 0.6", "laws": [1, 2]}, "REFUSED"),
                       ({"bound": "RL <= 1000", "tree": "x"}, "REFUSED"),
                       ({"bound": "VL*I <= 0.6", "laws": ["VL*I = 1", "VL = I*RL"]}, "REFUSED")):
        c = cert(junk)[0]
        assert c["verdict"] == word, (junk, c)
    big = {"split": "RL", "at": "2", "lo": {"leaf": "interval"}, "hi": {"leaf": "interval"}}
    for _ in range(16):
        big = {"split": "RL", "at": "2", "lo": big, "hi": big}
    c = cert({"bound": "RL <= 1000", "tree": big})[0]
    assert c["verdict"] == "REFUSED" and "nodes" in c["reason"], c
    r = zfl.run({"rows": [R("x", "[0,inf]")], "claim": "", "bounds": {"bound": "x <= 1"}})
    assert r["report"]["bounds"][0]["verdict"] == "REFUSED"
    print("   seven malformed certificates, an oversized tree, an infinite box: each REFUSED aloud, none raised")
    names = "abcd"
    rows3 = [R(n, "[1,2]") for n in names]
    worst = 0.0
    for k in (29, 32, 60, 200):
        x = "*".join(f"({names[i % 4]}-{1 + (i % 97) / 100:.2f})" for i in range(k))[:1990]
        t = time.time()
        zfl.run({"rows": rows3, "claim": "", "bounds": [{"bound": x + " <= 1/1000000"}] * 4})
        worst = max(worst, time.time() - t)
    assert worst < 3, worst
    print(f"   a public service: the worst probed document (products up to 200 factors, 4 certificates "
          f"asked, {zfl.MAX_CERTIFICATES} read) took {worst:.2f} s")


def _expr_for(text, rows):
    import zflcert
    q, _ = zflcert.parse_quantities(zfl.to_sheet(rows))
    e = zflcert._parse_arith(text, q)
    names = sorted(n for n in zflcert.ZC._names(e) if q[n]["lo"] < q[n]["hi"])
    return e, q, names


def sec11b_the_cap_counts_repeated_atoms():
    """2026-09-29, the curator: fix the studio's cap. The exact guarantee branches
    only on atoms named more than once (zverify._only, 27.09); E57 puts the hardness
    exactly there. So repeated atoms are capped at 10, all atoms at 64."""
    import random
    import time
    print("\n### 11b. The cap counts REPEATED atoms, not all of them")
    def rows(names, seed=1):
        rnd = random.Random(seed); out = []
        for n in names:
            s = rnd.choice(["verified", "unverified"])
            out.append({"name": n, "means": n, "status": s, **({"ground": "doc"} if s == "verified" else {})})
        return out
    def codes(doc):
        return [i["code"] for i in zfl.validate(doc)]
    once = [f"a{i}" for i in range(40)]
    ops = ["&", "|", "->", "^", "<->"]
    claim = once[0]
    for k, x in enumerate(once[1:]):
        claim = f"({claim} {ops[k % 5]} {x})"
    t0 = time.process_time()
    r = zfl.run({"claim": claim, "rows": rows(once)})
    assert r["ok"] and time.process_time() - t0 < 1.0, (r.get("issues"), time.process_time() - t0)
    # a read-once formula of 40 atoms is judged, not refused (refused before today)
    twice = [f"b{i}" for i in range(11)]
    rep = " & ".join(f"({x} | ~{x})" for x in twice)
    assert "E_TOOBIG" in codes({"claim": rep, "rows": rows(twice)})          # 11 repeated
    assert "E_TOOBIG" not in codes({"claim": " & ".join(f"({x} | ~{x})" for x in twice[:10]),
                                    "rows": rows(twice[:10])})              # 10 repeated
    # repeated ACROSS formulas counts too: once in the claim, once in a defined row
    split = {"claim": " & ".join(twice) + " & d",
             "rows": rows(twice) + [{"name": "d", "means": "d", "status": "defined", "ground": " | ".join(twice)}]}
    assert "E_TOOBIG" in codes(split), codes(split)
    many = [f"c{i}" for i in range(65)]
    assert "E_TOOBIG" in codes({"claim": " & ".join(many), "rows": rows(many)})   # 65 distinct
    # the hardest honest case that fits the length cap — MEASURED 0.66 s
    m = 5
    V = lambda p, h: f"x{p}_{h}"
    atoms = [V(p, h) for p in range(m + 1) for h in range(m)]
    cl = ["(" + " | ".join(V(p, h) for h in range(m)) + ")" for p in range(m + 1)]
    cl += [f"(~{V(p, h)} | ~{V(q, h)})" for h in range(m) for p in range(m + 1) for q in range(p + 1, m + 1)]
    php = f"({' & '.join(f'({x} | ~{x})' for x in atoms)}) -> ~({' & '.join(cl)})"
    c = codes({"claim": php, "rows": [{"name": x, "means": x, "status": "unverified"} for x in atoms]})
    assert "E_TOOBIG" in c or "E_TOOLONG" in c, c      # 30 repeated atoms: refused, not judged
    print("   40 atoms named once: judged; 11 named twice: refused; 10: judged;")
    print("   a repeat across claim and defined row counts; 65 distinct: refused.")

if __name__ == "__main__":
    print("=" * 72)
    print("ZFL v2 — the table, headless")
    print("=" * 72)
    sec1_one_table_three_instruments()
    sec2_the_cells_are_checked_where_the_eye_is()
    sec3_the_ledger_appears_when_it_is_wanted()
    sec3b_what_the_ground_column_is_actually_for()
    sec4_an_unknown_is_a_question_not_a_gap()
    sec4c_a_number_without_a_value_goes_back_to_the_translator()
    sec4d_a_name_that_multiplies_itself_is_one_number()
    sec4e_a_system_whose_coefficients_are_known_within_tolerance()
    sec7_the_ground_gate_demotes_phantom_words()
    sec7b_the_receipt_tells_what_was_said_from_what_was_done()
    sec7c_number_claims_carry_their_verdict_and_the_root_is_read()
    sec8_the_credit_that_cannot_be_redeemed()
    sec9_the_world_has_a_clock_too()
    sec10_what_the_ground_holds_and_what_to_check()
    sec11_a_public_service_cannot_be_made_to_raise_or_to_stall()
    sec11b_the_cap_counts_repeated_atoms()
    sec12_a_bound_over_the_whole_box_by_certificate()
    sec13_naive_sets_are_in_the_language()
    sec14_the_model_chain_moves_on()
    sec15_a_convention_changes_the_order_never_the_verdict()
    sec16_a_lone_equals_is_read_by_the_types_of_its_sides()
    sec17_a_clock_beside_a_numeric_claim_never_crashes()
    sec4b_every_example_runs_and_json_types_are_taken_as_they_come()
    sec5_the_spec_can_build_the_form_and_the_page()
    print("=" * 72)
    print("ZFL2 GREEN — one table, the genre computed rather than declared,")
    print("errors addressed to the cell the eye is on, and the numeric floor,")
    print("the passport office and the ledger all reachable without choosing")
    print("a tab or learning a syntax. The form and the reference page are")
    print("views over the same spec the validator enforces.")
