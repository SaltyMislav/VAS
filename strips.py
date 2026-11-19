"""STRIPS planer sa stogom ciljeva (goal-stack) i povratnim pretraživanjem.

Modul je potpuno neovisan o domeni: ne zna ništa o bazi, aplikaciji ni
scenarijima. Dobiva stanje (skup istinitih predikata), cilj (uređenu n-torku
predikata), listu operatora i opcionalno skup "vanjskih" predikata koje
planer ne može sam postići, nego samo čekati (pseudo-korak ``WAIT:<p>``).
"""
from dataclasses import dataclass

WAIT_PREFIX = "WAIT:"


@dataclass(frozen=True)
class Op:
    name: str
    pre: tuple          # uređeno: redoslijed preduvjeta je heuristika planera
    add: frozenset
    dele: frozenset

    def applicable(self, s):
        return set(self.pre) <= s

    def apply(self, s):
        return (s - self.dele) | self.add


def make_op(name, pre, add, dele=()):
    """Pomoćni konstruktor: prima obične liste/n-torke."""
    return Op(name, tuple(pre), frozenset(add), frozenset(dele))


def is_wait(step):
    return step.startswith(WAIT_PREFIX)


def wait_target(step):
    return step[len(WAIT_PREFIX):]


def _fmt_stack(stack):
    out = []
    for kind, x, _ in stack:
        if kind == "op":
            out.append(f"<{x.name}>")
        elif kind == "conj":
            out.append("&(" + ",".join(x) + ")")
        else:
            out.append(x)
    return "[" + " | ".join(out) + "]"


def strips(state, goal, ops, external=(), max_steps=25, trace=None):
    """Vrati plan (listu naziva akcija i WAIT koraka) ili None ako plan ne postoji.

    Elementi stoga su trojke (vrsta, sadržaj, preci):
      - ("goal", p, anc)  – jednostavan cilj p
      - ("conj", (p1..pn), anc) – provjera da konjunkcija i dalje vrijedi
      - ("op", Op, anc)   – operator koji treba primijeniti
    ``anc`` je skup ciljeva "iznad" trenutnog (za detekciju ciklusa).

    ``trace`` je opcionalna funkcija trace(tekst) za ispis tijeka pretrage.
    """
    external = set(external)

    def t(depth, text):
        if trace is not None:
            trace("  " * depth + text)

    def solve(state, stack, plan, depth):
        if not stack:
            return plan
        if len(plan) > max_steps:
            t(depth, f"BACKTRACK: plan dulji od {max_steps} koraka")
            return None
        (kind, x, anc), rest = stack[0], stack[1:]
        if trace is not None:
            t(depth, f"stog: {_fmt_stack(stack)}")

        if kind == "op":
            if x.applicable(state):
                t(depth, f"PRIMIJENI {x.name}")
                return solve(x.apply(state), rest, plan + [x.name], depth)
            t(depth, f"BACKTRACK: {x.name} nije primjenjiv "
                     f"(nedostaje {sorted(set(x.pre) - state)})")
            return None

        if kind == "conj":
            missing = [g for g in x if g not in state]
            if not missing:
                return solve(state, rest, plan, depth)
            t(depth, f"konjunkcija narušena, ponovno postižem {missing}")
            return solve(state, [("goal", g, anc) for g in missing] + stack, plan, depth)

        g = x
        if g in state:
            return solve(state, rest, plan, depth)
        if g in external:
            t(depth, f"cilj {g} je vanjski -> {WAIT_PREFIX}{g}")
            return solve(state | {g}, rest, plan + [f"{WAIT_PREFIX}{g}"], depth)
        if g in anc:
            t(depth, f"BACKTRACK: ciklus, {g} je već među precima")
            return None
        tried = False
        for op in ops:
            if g in op.add:
                tried = True
                t(depth, f"cilj {g}: pokušavam operator {op.name}")
                pre = sorted(op.pre, key=lambda p: p in external)
                sub = [("goal", p, anc | {g}) for p in pre]
                r = solve(
                    state,
                    sub + [("conj", op.pre, anc | {g}), ("op", op, anc)] + rest,
                    plan,
                    depth + 1,
                )
                if r is not None:
                    return r
                t(depth, f"cilj {g}: operator {op.name} nije uspio")
        t(depth, f"BACKTRACK: cilj {g} nije ostvariv"
                 + ("" if tried else " (nijedan operator ga ne dodaje)"))
        return None

    goal = tuple(goal)
    start = [("goal", g, frozenset()) for g in goal] + [("conj", goal, frozenset())]
    return solve(frozenset(state), start, [], 0)


def simulate(state, plan, ops):
    """Primijeni plan na stanje (WAIT koraci se preskaču). Diže ValueError
    ako neka akcija nije primjenjiva."""
    by_name = {op.name: op for op in ops}
    s = frozenset(state)
    for step in plan:
        if is_wait(step):
            continue
        op = by_name[step]
        if not op.applicable(s):
            raise ValueError(f"{step} nije primjenjiv u {sorted(s)}")
        s = op.apply(s)
    return s
