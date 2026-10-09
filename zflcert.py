# -*- coding: utf-8 -*-
"""A BOUND OVER THE WHOLE BOX, BY CERTIFICATE — the studio's side of ZTL's zcertify.

The decision of 2026-10-09: ZTL's kernel takes no budgets. It CHECKS a certificate,
exactly, whatever its size; it never searches. Search lives outside — here, in the
studio, with the budget of a public service. A document may bring its own tree (any
searcher, any tool) or leave the studio to look for one; either way the verdict is
the kernel's check, and the report says who found the tree.

    "bounds": {"bound": "V*V*RL/((Rs + RL)*(Rs + RL)) <= 0.6"}
    "bounds": {"bound": "VL*I <= 0.6", "laws": ["V - VL = I*Rs", "VL = I*RL"]}
    "bounds": {"bound": "...", "tree": {"split": "RL", "at": "10", "lo": ..., "hi": ...}}
(The document key is `bounds`: `certificate` is already a kind of ground in ZFL.)

The quantities are the document's rows: an interval value is a box, a number is
fixed, `?` is an unknown fixed by the linear `laws` (the kernel solves them itself).

Verdicts: CHECKED (the kernel accepted the tree: the bound holds on the whole box),
FAILS (the search met a point of the box where the bound is false — the value there
is the kernel's exact reading), NOT FOUND (the search ran out of its budget: nothing
is claimed either way), REFUSED (a brought tree the kernel rejected, with its reason).
"""
from fractions import Fraction
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "ztlcore"))

import zcertify as ZC                                   # noqa: E402
from znumjudge import _parse_arith, parse_quantities    # noqa: E402

MAX_PIECES = 2000        # the STUDIO's search budget per bound (a public request), not the kernel's
# THE COST IS IN THE SIZE OF THE DERIVATIVES, not in the count of pieces. MEASURED 2026-10-09:
# a product of 200 factors (1799 characters) has derivatives of 83 555 nodes, and ONE piece
# took 1.35 s (10-16 us per node read); the search over it, 10 s. So every piece is charged
# its node count — the expression plus each derivative — against one budget per DOCUMENT;
# a brought tree is charged at the door (leaves x nodes) and refused there when over it.
WORK_CAP = 400_000       # node-readings per document (search counted twice: the kernel re-reads)
MAX_NODES = 4000         # the expression and its derivatives, at the door: one piece stays cheap
MAX_DEPTH = 60
MAX_TREE_NODES = 20001   # a brought tree larger than this is refused at the door (request size)
_BOUND = re.compile(r"^(?P<lhs>.+?)\s*(?P<op><=|>=)\s*(?P<rhs>[^<>=]+)$")


class CertError(ValueError):
    pass


def _tree_nodes(t, cap):
    n, stack = 0, [t]
    while stack:
        x = stack.pop()
        n += 1
        if n > cap:
            return n
        if isinstance(x, dict) and "split" in x:
            stack += [x.get("lo"), x.get("hi")]
    return n


def parse(cert):
    """(expr text, op, bound Fraction, laws, tree|None) or CertError."""
    if not isinstance(cert, dict):
        raise CertError("certificate must be an object with a `bound`")
    m = _BOUND.match(str(cert.get("bound") or "").strip())
    if not m:
        raise CertError("bound must read `expression <= number` or `expression >= number`")
    try:
        bound = Fraction(m.group("rhs").strip())
    except (ValueError, ZeroDivisionError):
        raise CertError("the right side of the bound must be a number (3/5, 0.6)")
    laws = cert.get("laws") or []
    if not isinstance(laws, list) or not all(isinstance(l, str) for l in laws):
        raise CertError("laws must be a list of equalities")
    laws = [re.sub(r"(?<![=<>!])=(?!=)", "==", l) for l in laws]     # a lone `=` is the equality
    tree = cert.get("tree")
    if tree is not None and _tree_nodes(tree, MAX_TREE_NODES) > MAX_TREE_NODES:
        raise CertError(f"tree larger than {MAX_TREE_NODES} nodes: refused at the door")
    return m.group("lhs").strip(), m.group("op"), bound, laws, tree


def _size(e):
    n, stack = 0, [e]
    while stack:
        x = stack.pop()
        n += 1
        if isinstance(x, tuple):
            for a in x[1:]:
                stack.extend(a if isinstance(a, list) else [a])
    return n


def _search(e, qs, names, op, bound, work):
    """The studio's search: {"tree", "pieces"} | {"witness", "value"} | {"gave_up"}."""
    width0 = {n: qs[n]["hi"] - qs[n]["lo"] for n in names}
    derivs = {n: ZC.derivative(e, n) for n in names}
    # charged TWICE: the kernel then reads the same pieces again to check the tree
    per_piece = 2 * (_size(e) * 2 + sum(_size(d) for d in derivs.values()))
    bad = (lambda v: v > bound) if op == "<=" else (lambda v: v < bound)
    count = [0]

    class Stop(Exception):
        pass

    def value_at(point):
        r = ZC._reading(e, qs, {n: (v, v) for n, v in point.items()})
        return None if r is None else r[0]

    def go(piece, depth):
        count[0] += 1
        work[0] += per_piece
        if work[0] > WORK_CAP:
            raise Stop({"gave_up": f"the document's work budget ({WORK_CAP} node-readings) is spent"})
        if count[0] > MAX_PIECES or depth > MAX_DEPTH:
            raise Stop({"gave_up": f"more than {MAX_PIECES} pieces" if count[0] > MAX_PIECES
                        else f"deeper than {MAX_DEPTH} splits"})
        signs, straddle = {}, []
        for n in names:
            lo, hi = piece[n]
            if lo == hi:
                continue
            r = ZC._reading(derivs[n], qs, piece)
            if r is not None and r[0] >= 0:
                signs[n] = "+"
            elif r is not None and r[1] <= 0:
                signs[n] = "-"
            else:
                straddle.append(n)
        if not straddle:
            corner = {n: (piece[n][1] if (signs.get(n) == "+") == (op == "<=") else piece[n][0]) for n in names}
            v = value_at(corner)
            if v is not None and bad(v):
                raise Stop({"witness": corner, "value": v})
            return {"leaf": "monotone", "signs": signs}
        r = ZC._reading(e, qs, piece)
        if r is not None and (r[1] <= bound if op == "<=" else r[0] >= bound):
            return {"leaf": "interval"}
        mid = {n: (lo + hi) / 2 for n, (lo, hi) in piece.items()}
        v = value_at(mid)
        if v is not None and bad(v):
            raise Stop({"witness": mid, "value": v})
        rel = lambda k: (piece[k][1] - piece[k][0]) / width0[k]
        n = max(straddle, key=rel)
        other = max((k for k in names if piece[k][0] < piece[k][1]), key=rel)
        if rel(other) > 8 * rel(n):
            n = other
        lo, hi = piece[n]
        at = (lo + hi) / 2
        return {"split": n, "at": f"{at.numerator}/{at.denominator}",
                "lo": go(dict(piece, **{n: (lo, at)}), depth + 1),
                "hi": go(dict(piece, **{n: (at, hi)}), depth + 1)}

    try:
        tree = go({n: (qs[n]["lo"], qs[n]["hi"]) for n in names}, 0)
    except Stop as s:
        return s.args[0]
    return {"tree": tree, "pieces": count[0]}


def _s(x):
    return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"


def run_all(certs, sheet):
    """Every certificate of one document, under ONE work budget."""
    work = [0]
    return [run(c, sheet, work) for c in certs]


def run(cert, sheet, work=None):
    """The report entry for one certificate over the document's quantities."""
    work = [0] if work is None else work
    try:
        text, op, bound, laws, tree = parse(cert)
    except CertError as err:
        return {"verdict": "REFUSED", "reason": str(err)}
    q, _m = parse_quantities(sheet)
    unknowns = sorted(n for n, v in q.items() if v["lo"] == float("-inf") and v["hi"] == float("inf"))
    out = {"bound": f"{text} {op} {_s(bound)}"}
    try:
        if laws:
            sol = ZC.solve_system(laws, unknowns, q)
            e = ZC._subst(_parse_arith(text, q), sol)
        else:
            e = _parse_arith(text, q)
    except (ZC.SystemError_, ValueError) as err:
        return dict(out, verdict="REFUSED", reason=f"cannot read: {err}")
    names = sorted(n for n in ZC._names(e) if n in q and q[n]["lo"] < q[n]["hi"])
    nodes = _size(e) * 2 + sum(_size(ZC.derivative(e, n)) for n in names)
    if nodes > MAX_NODES:
        return dict(out, verdict="REFUSED",
                    reason=f"the expression and its derivatives come to {nodes} nodes, over the public "
                           f"studio's {MAX_NODES} — the ZTL kernel (zcertify.py) takes it locally, with no budget")
    if ZC._names(e) & set(unknowns):
        return dict(out, verdict="REFUSED",
                    reason="an unknown (`?`) that no law fixes: give the linear laws that determine it")
    for n in names:
        if isinstance(q[n]["lo"], float) or isinstance(q[n]["hi"], float):
            return dict(out, verdict="REFUSED", reason=f"{n} is unbounded: no certificate covers an infinite box")
    found_by = "brought with the document"
    if tree is not None:
        leaves = (_tree_nodes(tree, MAX_TREE_NODES) + 1) // 2
        cost = leaves * (_size(e) * 2 + sum(_size(ZC.derivative(e, n)) for n in names))
        work[0] += cost
        if work[0] > WORK_CAP:
            return dict(out, verdict="REFUSED", found_by=found_by,
                        reason=f"checking this tree costs about {cost} node-readings, over the public "
                               f"studio's {WORK_CAP} per document — the ZTL kernel (zcertify.py) checks it "
                               "locally, with no budget at all")
    if tree is None:
        got = _search(e, q, names, op, bound, work)
        if "witness" in got:
            return dict(out, verdict="FAILS", found_by="the studio's search",
                        at={k: _s(v) for k, v in got["witness"].items()}, value_there=_s(got["value"]),
                        note="the value at this point of the box is the kernel's exact reading")
        if "gave_up" in got:
            return dict(out, verdict="NOT FOUND", found_by="the studio's search",
                        reason=f"no certificate within the studio's budget ({got['gave_up']}); "
                               "nothing is claimed either way — bring a tree from your own search")
        tree, found_by = got["tree"], "the studio's search"
    if laws:
        ok, info = ZC.check_system(text, laws, unknowns, q, op, bound, tree)
    else:
        ok, info = ZC.check(e, q, op, bound, tree)
    if not ok:
        return dict(out, verdict="REFUSED", found_by=found_by, reason=f"the kernel rejected the tree: {info}")
    prov = sorted({q[n]["prov"] for n in names})
    return dict(out, verdict="CHECKED", found_by=found_by, pieces=info,
                checked_by="the ZTL kernel, exactly (fractions), no budget" +
                           ("; it solved the linear laws itself" if laws else ""),
                rests_on="the boxes of " + ", ".join(names) + f" ({'/'.join(prov)})",
                **({"tree": tree} if found_by == "the studio's search" and _tree_nodes(tree, 200) <= 200 else {}))
