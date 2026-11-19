import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from domain import (ALL_OPS, EXTERNAL_APP, G_APP, G_BAZA, OPS_APP, OPS_BAZA,  # noqa: E402
                    OWNER, PREDICATES)
from strips import is_wait, simulate, strips  # noqa: E402


def s0(n):
    return set(json.loads((ROOT / "scenarios" / f"s{n}.json").read_text(encoding="utf-8"))["initial_state"])


def plan_baza(state, **kw):
    return strips(state, G_BAZA, OPS_BAZA, **kw)


def plan_app(state, **kw):
    return strips(state, G_APP, OPS_APP, external=EXTERNAL_APP, **kw)


EXPECTED = {
    (1, "baza"): ["ObnoviIzBackupa", "PopraviKonfigBaze", "PokreniBazu",
                  "ProvjeriIntegritet", "OznaciSpremnom"],
    (1, "app"): ["ZaustaviAplikaciju", "VratiKonfigIzBackupa", "PokreniAplikaciju",
                 "WAIT:BazaSpremna", "PoveziSBazom", "ProvjeriRadSustava"],
    (2, "baza"): ["ZamijeniDisk", "ObnoviIzReplike", "PokreniBazu",
                  "ProvjeriIntegritet", "OznaciSpremnom"],
    (2, "app"): ["ReinstalirajAplikaciju", "GenerirajKonfigIzPredloska", "PokreniAplikaciju",
                 "WAIT:BazaSpremna", "PoveziSBazom", "ProvjeriRadSustava"],
    (3, "baza"): ["ZaustaviBazu", "ObnoviIzBackupa", "PokreniBazu",
                  "ProvjeriIntegritet", "OznaciSpremnom"],
    (3, "app"): ["WAIT:BazaSpremna", "ProvjeriRadSustava"],
    (4, "baza"): None,
}


@pytest.mark.parametrize("n,who", list(EXPECTED))
def test_ocekivani_planovi(n, who):
    plan = plan_baza(s0(n)) if who == "baza" else plan_app(s0(n))
    assert plan == EXPECTED[(n, who)]


def test_s3_replan_aplikacije_nakon_db_ready():
    """Nakon što baza izvrši svoj plan (ZaustaviBazu briše vezu), aplikacija
    iz novog stanja mora planirati ponovno povezivanje."""
    state = simulate(s0(3), plan_baza(s0(3)), OPS_BAZA)
    assert "BazaSpremna" in state and "VezaUspostavljena" not in state
    assert plan_app(state) == ["PoveziSBazom", "ProvjeriRadSustava"]


def test_s4_aplikacija_samo_ceka_bazu():
    plan = plan_app(s0(4))
    assert plan[0] == "WAIT:BazaSpremna"


@pytest.mark.parametrize("n", [1, 2, 3])
def test_simulacija_plana_baze_postize_cilj(n):
    state = s0(n)
    final = simulate(state, plan_baza(state), OPS_BAZA)
    assert set(G_BAZA) <= final


@pytest.mark.parametrize("n", [1, 2, 3])
def test_simulacija_plana_aplikacije_postize_cilj(n):
    """Plan aplikacije bez WAIT koraka, uz ručno dodan BazaSpremna, postiže G_APP."""
    state = s0(n)
    plan = [a for a in plan_app(state) if not is_wait(a)]
    final = simulate(state | {"BazaSpremna"}, plan, OPS_APP)
    assert set(G_APP) <= final


@pytest.mark.parametrize("n", [1, 2, 3])
def test_zajednicko_izvrsavanje_postize_zajednicki_cilj(n):
    """Slijedno: plan baze, pa (re)plan aplikacije iz dobivenog stanja."""
    state = simulate(s0(n), plan_baza(s0(n)), OPS_BAZA)
    state = simulate(state, plan_app(state), OPS_APP)
    assert set(G_BAZA) | set(G_APP) <= state


def test_planer_ne_ovisi_o_scenariju_replika_umjesto_backupa():
    state = (s0(1) - {"BackupBaze"}) | {"ReplikaDostupna"}
    plan = plan_baza(state)
    assert "ObnoviIzReplike" in plan and "ObnoviIzBackupa" not in plan
    assert set(G_BAZA) <= simulate(state, plan, OPS_BAZA)


def test_planer_ne_ovisi_o_scenariju_predlozak_umjesto_backupa_konfiguracije():
    state = (s0(1) - {"BackupKonfigApp"}) | {"PredlozakKonfigApp"}
    plan = plan_app(state)
    assert "GenerirajKonfigIzPredloska" in plan and "VratiKonfigIzBackupa" not in plan


def test_cilj_vec_ispunjen_daje_prazan_plan():
    assert plan_baza(set(G_BAZA) | {"BazaPokrenuta"}) == []


def test_bez_external_aplikacija_nema_plan():
    """Bez WAIT mehanizma aplikacija ne može sama postići BazaSpremna."""
    assert strips(s0(1), G_APP, OPS_APP) is None


def test_planer_je_genericki_druga_domena():
    from strips import make_op
    ops = [make_op("a", ["x"], ["y"]), make_op("b", ["y"], ["z"], ["x"])]
    assert strips({"x"}, ("z",), ops) == ["a", "b"]
    assert strips(set(), ("z",), ops) is None


def test_trace_ne_mijenja_plan_i_biljezi_backtrack():
    lines = []
    assert plan_baza(s0(4), trace=lines.append) is None
    assert any("BACKTRACK" in line for line in lines)
    lines = []
    assert plan_baza(s0(1), trace=lines.append) == EXPECTED[(1, "baza")]
    assert lines


def test_domena_je_konzistentna():
    assert len(OPS_BAZA) >= 6 and len(OPS_APP) >= 6
    assert set(OWNER) == set(ALL_OPS)
    for op in ALL_OPS.values():
        assert set(op.pre) | op.add | op.dele <= set(PREDICATES), op.name
    for n in range(1, 5):
        assert s0(n) <= set(PREDICATES)
