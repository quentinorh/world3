"""Le scenario standard reste intact, et une decision prise en 2026 ne reecrit pas 2000."""

import numpy as np
from pyworld3 import World3

from world3.anims import SCENES, catalog
from world3.content import (
    EVENTS,
    FORKS,
    INTRO,
    ISS_CARD,
    LAWS,
    SHOCKS,
    iss_visible,
    apply_document,
    choice_parts,
    document,
    gap_event_count,
    next_stop,
    plan_events,
    pressure,
    resolve_event,
    roll_shock,
)
from world3.sim import (
    LAW_IDS,
    StewardsWorld,
    active_kinds,
    baseline_schedule,
    clear_cache,
    judge,
    policy_from,
    run_schedule,
    satellite_count,
    talk_lines,
)


def _event_continue_resumes():
    """Continuer un evenement relance la Terre jusqu'au prochain arret."""
    import tempfile
    from pathlib import Path

    from world3.app import TURN_SPIN, YEAR_PACE, App
    from world3.save import GameState

    app = App.__new__(App)
    app.audio = False
    app.state = GameState(Path(tempfile.gettempdir()) / "world3_event_resume.json")
    app.state.year = 2028.0
    app.state.pending = (2028.0, "iag")
    app.state.seen_intro = True
    app.stops = [("event", 2029.0, "fusion"), ("conseil", 2030.0, None)]
    app.shock = {"id": "iag"}
    app.overlay = "shock"
    app.turn_anim = None
    app.spin = 0.04
    app.screen = "monde"
    app._hold_depart = False
    app.stats_open = False
    app.stats_t = 0.0
    app._stats_anim = None
    app._traj = object()
    app._traj_key = object()
    app.dirty = False
    app._turn_heard = False
    app.dismiss_shock()
    assert app.overlay is None and app.shock is None and app.state.pending is None
    assert any(sid == "iag" for _year, sid in app.state.shocks)
    assert app.turn_anim is not None
    origin, dest, _elapsed, dur = app.turn_anim
    assert origin == 2028.0 and dest == 2029.0
    assert abs(dur - (dest - origin) * YEAR_PACE) < 1e-9
    assert app.stops[0] == ("event", 2029.0, "fusion")
    assert app.spin <= TURN_SPIN + 1e-6

    app.state.year = 2029.0
    app.stops = []
    app.state.pending = (2029.0, "fusion")
    app.overlay = "shock"
    app.shock = {"id": "fusion"}
    app.turn_anim = None
    app.dismiss_shock()
    assert app.turn_anim is not None
    origin, dest, _elapsed, dur = app.turn_anim
    assert origin == 2029.0 and dest > 2029.0
    assert abs(dur - (dest - origin) * YEAR_PACE) < 1e-9
    assert app.stops[-1][0] in ("conseil", "fin")


def _shock_card_effect():
    """La carte d'événement compare le monde avec et sans le choc."""
    import tempfile
    from pathlib import Path

    from world3.app import App
    from world3.save import GameState

    app = App.__new__(App)
    app.state = GameState(Path(tempfile.gettempdir()) / "world3_shock_card.json")
    app.state.year = 2030.0
    app.shock = {"id": "iag", "year": 2030}
    app._traj = None
    app._traj_key = None
    preview = app.shock_traj()
    committed = app.traj()
    assert preview is not None
    assert preview.sample(2036)["iopc"] > committed.sample(2036)["iopc"]
    assert preview.sample(2050)["nrfr"] < committed.sample(2050)["nrfr"]
    assert abs(preview.sample(2000)["iopc"] - committed.sample(2000)["iopc"]) < 1.0
    app.state.shocks = [(2030.0, "iag")]
    app._shock_key = None
    assert app.shock_traj() is None


def _iss_choice():
    """Garder laisse la station. Lâcher l'enlève, puis le dilemme de l'année s'ouvre."""
    import tempfile
    from pathlib import Path

    from world3.app import App
    from world3.save import GameState

    assert ISS_CARD["id"] == "iss"
    assert ISS_CARD["id"] not in {ev["id"] for ev in EVENTS}
    assert "iss" not in {s["id"] for s in SHOCKS}
    assert iss_visible([], 2040)
    assert iss_visible([(2030.0, "iss")], 2029)
    assert not iss_visible([(2030.0, "iss")], 2030)
    clear_cache()
    kept = run_schedule(baseline_schedule())
    dropped = run_schedule(baseline_schedule(), ((2030.0, "iss"),))
    for key in ("pop", "fpc", "iopc", "ppolx", "nrfr"):
        assert abs(kept.sample(2000)[key] - dropped.sample(2000)[key]) < 1.0, key
        assert abs(kept.sample(2050)[key] - dropped.sample(2050)[key]) < 1e-4, (key, kept.sample(2050)[key], dropped.sample(2050)[key])

    def make(path):
        if path.exists():
            path.unlink()
        app = App.__new__(App)
        app.audio = False
        app.state = GameState(path)
        app.state.year = 2030.0
        app.law = 0
        app.knob = 0.0
        app._traj = None
        app._traj_key = None
        app._choice_key = None
        app.council_phase = "dilemma"
        app.overlay = "event"
        app.event_prev = None
        app.event_pan = 0.0
        app.event_anim = None
        app.pick = None
        app.title = None
        return app

    app = make(Path(tempfile.gettempdir()) / "world3_iss_keep.json")
    app.open_dilemma()
    assert app.event["id"] == "iss"
    app.choose("a")
    assert "iss" in app.state.events_done
    assert app.state.shocks == []
    assert app.event["id"] == "greniers"
    assert app.overlay == "event"
    assert app.event_anim is not None
    assert app.event_prev is not None and app.event_prev["id"] == "iss"
    assert iss_visible(app.state.shocks, 2030)
    app._advance_event_slide(1.0)
    assert app.event_anim is None
    assert app.event_prev is None
    app.choose("b")
    assert app.event["id"] == "conflit"
    assert app.event_anim is not None

    app = make(Path(tempfile.gettempdir()) / "world3_iss_drop.json")
    app.event = dict(ISS_CARD)
    app.event["year"] = 2030
    app.choose("b")
    assert any(sid == "iss" for _year, sid in app.state.shocks)
    assert not iss_visible(app.state.shocks, 2030)
    assert app.event["id"] == "greniers"
    assert app.overlay == "event"
    assert app.event_anim is not None
    assert app.event_prev is not None and app.event_prev["id"] == "iss"


def _world(schedule, shocks=()):
    world = StewardsWorld(tuple((float(year), notches) for year, notches in schedule), shocks)
    world.init_world3_constants()
    world.init_world3_variables()
    world.set_world3_table_functions()
    world.set_world3_delay_functions(method="euler")
    world.run_world3(fast=True)
    return world


def word(year, schedule=None):
    traj = run_schedule(schedule or baseline_schedule())
    return judge(traj.sample(year), traj.sample(year - 5), year)


def main():
    items = catalog()
    keys = [item["key"] for item in items]
    assert len(keys) == len(set(keys))
    assert set(keys) == set(SCENES), set(keys) ^ set(SCENES)

    base = run_schedule(baseline_schedule())
    world = World3(dt=1, verbose=False)
    world.init_world3_constants()
    world.init_world3_variables()
    world.set_world3_table_functions()
    world.set_world3_delay_functions(method="euler")
    world.run_world3(fast=True)
    for name in ("pop", "fpc", "iopc", "ppolx", "nrfr"):
        err = float(np.nanmax(np.abs(getattr(base, name) - getattr(world, name))))
        assert err == 0.0, (name, err)

    care = ((1900.0, (0, 0, 0, 0, 0)), (2026.0, (3, 1, 2, 3, 3)))
    later = run_schedule(care)
    assert abs(base.sample(2000)["pop"] - later.sample(2000)["pop"]) < 1.0

    tech = ((1900.0, (0,) * 10), (2026.0, (0, 0, 0, 0, 0, 0, 0, 4, 0, 0)))
    lifted = run_schedule(tech)
    assert abs(base.sample(2000)["iopc"] - lifted.sample(2000)["iopc"]) < 1.0
    assert lifted.sample(2030)["iopc"] > base.sample(2030)["iopc"]

    assert word(1970) == "CROISSANCE", word(1970)
    assert word(2026) == "TENSION", word(2026)
    assert word(2050) == "FAMINE", word(2050)
    # Cinq crans moderes en 2026 : l'inertie fait qu'en 2050 on mange juste,
    # mais la famine du scenario standard est evitee.
    cared = word(2050, care)
    assert cared not in ("FAMINE", "CRISE"), cared
    assert later.sample(2050)["fpc"] > 400
    assert word(2070, care) not in ("FAMINE",), word(2070, care)
    said = talk_lines(base.sample(2026), base.sample(2021))
    assert said and all(said)
    years = [ev["year"] for ev in EVENTS]
    assert years == sorted(years)
    assert all(year % 10 == 0 for year in years)
    assert len({ev["id"] for ev in EVENTS}) == len(EVENTS)
    assert len(SHOCKS) == 24
    assert len({s["id"] for s in SHOCKS}) == len(SHOCKS)

    def px(text, scale):
        return len(text) * 6 * scale - scale

    for shock in SHOCKS:
        assert px(shock["title"], 4) < 680, shock["title"]
        for line in shock["lines"]:
            assert px(line, 3) < 680, line
        assert px(shock["effect"], 2) < 680, shock["effect"]
        assert px(shock["banner"], 2) < 440, shock["banner"]

    again = roll_shock(7, 2026, 2031, set())
    assert again == roll_shock(7, 2026, 2031, set())
    seen_ids = set()
    for seed in range(60):
        rolled = roll_shock(seed, 2026, 2031, set())
        if rolled is None:
            continue
        when, sid = rolled
        assert 2026.2 <= when <= 2031
        seen_ids.add(sid)
        blocked = roll_shock(seed, 2026, 2031, {sid})
        if blocked is not None:
            assert blocked[1] != sid
    assert len(seen_ids) >= 8, seen_ids

    # Le passe d'avant l'evenement ne bouge pas. Chaque choc se voit en 2060.
    # (indicateur, signe, annee). L'IAG fait d'abord plus d'objets, puis vide les mines.
    expect = {
        "iag": ("iopc", 1, 2036),
        "fusion": ("nrfr", 1, 2050),
        "pandemie": ("pop", -1, 2036),
        "climat": ("fpc", -1, 2050),
        "guerre": ("iopc", -1, 2050),
        "paix": ("iopc", 1, 2050),
        "secheresse": ("fpc", -1, 2050),
        "gisement": ("nrfr", 1, 2050),
        "filon": ("nrfr", -1, 2050),
        "accord": ("ppolx", -1, 2050),
        "accident": ("ppolx", 1, 2050),
        "ecoles": ("pop", -1, 2050),
        "baby": ("pop", 1, 2050),
        "medecine": ("pop", 1, 2050),
        "insectes": ("fpc", -1, 2050),
        "circulaire": ("nrfr", 1, 2050),
        "krach": ("iopc", -1, 2050),
        "barrages": ("fpc", 1, 2050),
        "charbon": ("ppolx", 1, 2050),
        "batteries": ("nrfr", 1, 2050),
        "erosion": ("fpc", -1, 2050),
        "vaccin": ("pop", 1, 2050),
        "spatial": ("nrfr", 1, 2050),
        "jetable": ("iopc", -1, 2050),
    }
    assert set(expect) == {s["id"] for s in SHOCKS}
    for sid, (key, sign, year) in expect.items():
        clear_cache()
        shocked = run_schedule(baseline_schedule(), ((2030.0, sid),))
        assert abs(base.sample(2000)[key] - shocked.sample(2000)[key]) < 1.0, sid
        before = base.sample(year)[key]
        after = shocked.sample(year)[key]
        delta = after - before
        assert delta * sign > 0, (sid, key, year, before, after)
        assert abs(delta) / max(abs(before), 1e-9) > 0.004, (sid, key, year, before, after)
    clear_cache()
    iag = run_schedule(baseline_schedule(), ((2030.0, "iag"),))
    assert iag.sample(2050)["nrfr"] < base.sample(2050)["nrfr"] * 0.8

    cards = list(EVENTS) + list(FORKS.values())
    for ev in cards:
        assert px(ev["title"], 4) < 680, ev["title"]
        for line in ev["lines"]:
            assert px(line, 3) < 660, line
        for key in ("a", "b"):
            label, _index, _delta, sub, _shock = choice_parts(ev[key])
            assert px(label, 3) < 600, label
            assert px(sub, 2) < 580, sub

    # Deep-mining : le metal arrive sur quinze ans, pas d'un coup. Les usines
    # tiennent au lieu d'exploser, et l'air monte un peu plus. Fumees le rattrape.
    filons = run_schedule(baseline_schedule(), ((2030.0, "filons"),))
    assert abs(base.sample(2000)["pop"] - filons.sample(2000)["pop"]) < 1.0
    assert filons.sample(2031)["iopc"] < base.sample(2031)["iopc"] * 1.06
    assert filons.sample(2031)["nrfr"] < base.sample(2031)["nrfr"] + 0.02
    assert filons.sample(2040)["nrfr"] > base.sample(2040)["nrfr"] + 0.05
    assert filons.sample(2055)["nrfr"] > base.sample(2055)["nrfr"]
    assert base.sample(2050)["iopc"] * 1.3 < filons.sample(2050)["iopc"] < base.sample(2050)["iopc"] * 2.0
    assert filons.sample(2055)["ppolx"] > base.sample(2055)["ppolx"] + 0.5
    aired = ((1900.0, (0,) * 10), (2030.0, (0, 0, 0, 4, 0, 0, 0, 0, 0, 0)))
    clean = run_schedule(aired, ((2030.0, "filons"),))
    assert clean.sample(2055)["ppolx"] < filons.sample(2055)["ppolx"] - 1.5
    assert clean.sample(2070)["fpc"] > filons.sample(2070)["fpc"]

    # Le monde stable tient. Toutes les techniques, sans frein : la chute
    # arrive quand meme, plus tard. L'industrie fond, le mot n'est plus STABLE.
    stable = ((1900.0, (0,) * 10), (2026.0, (4, 4, 2, 4, 4, 4, 4, 0, 0, 0)))
    held_word = word(2080, stable)
    assert held_word in ("STABLE", "RALENTISSEMENT"), held_word
    assert run_schedule(stable).sample(2080)["fpc"] > 400
    boom = run_schedule(
        ((1900.0, (0,) * 10), (2026.0, (0, 0, 4, 4, 4, 0, 0, 2, 0, 1))),
        ((2026.0, "filons"),),
    )
    assert boom.sample(2100)["iopc"] < boom.sample(2040)["iopc"] * 0.5
    assert word(2100, ((1900.0, (0,) * 10), (2026.0, (0, 0, 4, 4, 4, 0, 0, 2, 0, 1)))) != "STABLE"
    assert judge(boom.sample(2060), boom.sample(2055), 2060) != "STABLE"

    # Cran 4 plafonne le souhait a 2. Il fait moins de gens que le cran 3.
    notch3 = ((1900.0, (0,) * 10), (2026.0, (3, 0, 0, 0, 0, 0, 0, 0, 0, 0)))
    notch4 = ((1900.0, (0,) * 10), (2026.0, (4, 0, 0, 0, 0, 0, 0, 0, 0, 0)))
    assert run_schedule(notch4).sample(2100)["pop"] < run_schedule(notch3).sample(2100)["pop"]
    capped = _world(notch4)
    assert float(capped.dcfs[2100 - 1900 - 1]) <= 2.0 + 1e-6

    # Usines : la duree de vie monte sur dix ans, puis le stock n'augmente plus.
    plants = _world(((1900.0, (0,) * 10), (2026.0, (0, 4, 0, 0, 0, 0, 0, 0, 0, 0))))
    assert 14.0 < float(plants.alic[2031 - 1900]) < 28.0
    assert float(plants.alic[2036 - 1900]) >= 28.0 - 1e-6
    assert float(plants.ic[2036 - 1900]) <= float(plants.ic[2026 - 1900]) * 1.03
    assert float(plants.ic[2046 - 1900]) <= float(plants.ic[2036 - 1900]) * 1.005

    # Inertie : un cran pose une cible, le parametre y glisse en ligne droite
    # depuis la valeur effective au conseil. Un second cran repart de la.
    tech4 = (0, 0, 0, 0, 0, 0, 0, 4, 0, 0)
    ramped = _world(((1900.0, (0,) * 10), (2030.0, tech4)))
    assert abs(float(ramped.icor[2030 - 1900]) - 3.0) < 1e-6
    mid = float(ramped.icor[2036 - 1900])
    assert 1.8 < mid < 3.0, mid
    assert abs(mid - 2.4) < 0.02, mid
    assert abs(float(ramped.icor[2042 - 1900]) - 1.8) < 1e-6
    assert ramped.iopc[2031 - 1900] < base.sample(2031)["iopc"] * 1.08
    back = StewardsWorld(((1900.0, (0,) * 10), (2030.0, tech4), (2036.0, (0,) * 10)))
    assert abs(back.policy_at(2036.0).icor - mid) < 0.02
    assert 1.8 < back.policy_at(2040.0).icor < 3.0
    assert abs(back.policy_at(2048.0).icor - 3.0) < 1e-9
    assert back.policy_at(2036.0).fcest == 4000.0
    # Le plafond a deux enfants monte en force avec la norme.
    locked = StewardsWorld(((1900.0, (0,) * 10), (2030.0, (4,) + (0,) * 9)))
    assert locked.lock_at(2030.0) == 0.0
    assert 0.4 < locked.lock_at(2036.0) < 0.6
    assert locked.lock_at(2042.0) == 1.0

    # Evenement a montee : rien l'annee meme, tout apres `ramp`.
    fused = StewardsWorld(baseline_schedule(), ((2030.0, "fusion"),))
    assert fused.fx_at(2029.0) is None
    assert abs(fused.fx_at(2030.0)["nruf"] - 1.0) < 1e-9
    half = fused.fx_at(2037.5)["nruf"]
    assert 0.55 < half < 1.0 and abs(half - 0.775) < 1e-6, half
    assert abs(fused.fx_at(2045.0)["nruf"] - 0.55) < 1e-9
    assert abs(fused.fx_at(2080.0)["ppgf"] - 0.70) < 1e-9
    # Deep-mining : le metal arrive au prorata des annees, et une part du
    # capital part creuser.
    deep = StewardsWorld(baseline_schedule(), ((2030.0, "filons"),))
    assert deep.nri_drip(2029.0, 2030.0) == 0.0
    assert abs(deep.nri_drip(2030.0, 2031.0) - 0.2 / 15) < 1e-9
    assert abs(deep.nri_drip(2030.0, 2045.0) - 0.2) < 1e-9
    assert abs(deep.nri_drip(2020.0, 2100.0) - 0.2) < 1e-9
    assert deep.nri_drip(2045.0, 2046.0) == 0.0
    assert abs(deep.fx_at(2037.5)["fcaor_add"] - 0.04) < 1e-9
    assert abs(deep.fx_at(2050.0)["fcaor_add"] - 0.08) < 1e-9
    dug = _world(baseline_schedule(), ((2030.0, "filons"),))
    assert abs(float(dug.nri) - float(plain_nri := _world(baseline_schedule()).nri) * 1.2) < 1e-6 * plain_nri
    # Un choc de stock reste instantane, meme avec les nouvelles clefs.
    sick = StewardsWorld(baseline_schedule(), ((2030.0, "pandemie"),))
    assert sick.oneshot(2029.0, 2030.0)[0] == 0.88
    assert sick.oneshot(2030.0, 2031.0) is None

    # Services prend sur les usines neuves. La part des champs, elle, ne sert pas de variable.
    fed = _world(((1900.0, (0,) * 10), (2026.0, (0, 0, 0, 0, 0, 0, 4, 0, 0, 0))))
    plain = _world(baseline_schedule())
    # Un budget se reoriente en cinq ans : rien l'annee meme, tout en 2031.
    year = 2026 - 1900
    assert abs(float(fed.fioas[year]) - float(plain.fioas[year])) < 1e-9
    year = 2027 - 1900
    assert abs(float(fed.fioaa[year]) - float(plain.fioaa[year])) < 1e-9
    assert float(fed.fioas[year]) > float(plain.fioas[year]) + 0.01
    year = 2031 - 1900
    assert abs(float(fed.fioaa[year]) - float(plain.fioaa[year])) < 0.01
    assert float(fed.fioas[year]) > float(plain.fioas[year]) + 0.05
    assert float(fed.fioai[year]) < float(plain.fioai[year]) - 0.05

    slow = {
        "pop": 6.0e9,
        "fpc": 450.0,
        "iopc": 160.0,
        "ppolx": 2.0,
        "nrfr": 0.30,
    }
    earlier = dict(slow)
    earlier["pop"] = 6.0e9 / (1.0 - 0.009 * 5.0)
    assert judge(slow, earlier, 2050) == "STABLE"
    earlier["pop"] = 6.0e9 / (1.0 - 0.02 * 5.0)
    assert judge(slow, earlier, 2050) != "STABLE"

    loud = {"ppolx": 18.0, "fpc": 420.0, "nrfr": 0.55, "iopc": 450.0, "pop": 8e9}
    assert pressure(loud) == "pollution"
    assert resolve_event(EVENTS[0], loud, (0,) * 10)["title"] == "L'AIR"
    quiet = base.sample(2030)
    assert pressure(quiet) in ("calme", "metal")
    assert choice_parts(resolve_event(EVENTS[0], quiet, (0,) * 10)["a"])[4] == "filons"
    assert next_stop(2026, 2100) == ("conseil", 2030.0)
    assert next_stop(2030, 2100) == ("conseil", 2040.0)
    assert next_stop(2096, 2100)[0] == "fin"
    assert next_stop(2100, 2150) == ("conseil", 2110.0)
    _event_continue_resumes()
    _shock_card_effect()
    _iss_choice()
    first = plan_events(7, 2026, 2030, set())
    assert first == plan_events(7, 2026, 2030, set())
    for when, sid in first:
        assert 2026.5 < when < 2029.8
        assert sid
    seen = 0
    decade = []
    for seed in range(40):
        seen += len(plan_events(seed, 2026, 2100, set()))
        gap = plan_events(seed, 2030, 2040, set())
        assert len(gap) <= 3
        assert len(plan_events(seed, 2026, 2030, set())) <= 3
        decade.append(len(gap))
    assert 10 <= seen / 40 <= 24, seen / 40
    assert 1.2 <= sum(decade) / len(decade) <= 2.8, sum(decade) / len(decade)
    assert gap_event_count([(2032.0, "a"), (2034.0, "b"), (2030.0, "c")], 2040) == 2
    ids = {s["id"] for s in SHOCKS[:2]}
    full = plan_events(3, 2036.0, 2040.0, ids)
    rest = plan_events(3, 2036.0, 2040.0, ids, before=2)
    assert rest == full[:1]
    assert plan_events(3, 2036.0, 2040.0, ids, before=3) == []
    for _title, lines in INTRO:
        for line in lines:
            assert px(line, 3) < 680, line

    if active_kinds() == LAW_IDS:
        assert policy_from((0,) * 10).dcfsn == 4.0
        assert policy_from((4,) + (0,) * 9).pop_lock
        assert satellite_count((0, 0, 0, 0, 0, 0, 0, 4, 0, 0)) == 64
    snap = document()
    try:
        apply_document(
            {
                "orientations": [
                    {"id": "terres", "kind": "terres", "title": "CHAMPS"},
                    {"id": "naissances", "kind": "foyers", "title": "NAISSANCES"},
                ]
            }
        )
        assert [law["kind"] for law in LAWS] == ["terres", "foyers"]
        assert LAWS[1]["title"] == "NAISSANCES"
        pol = policy_from((3, 4))
        assert pol.lyf == 1.6 and pol.pop_lock and pol.dcfsn == 2.0
        assert pol.alic == 14.0 and pol.ppgf == 1.0
        assert active_kinds() == ("terres", "foyers")
    finally:
        apply_document(snap)
    assert active_kinds() == tuple(LAW_IDS)
    assert len(LAWS) == 10

    print("ok", "2026", word(2026), "2050", word(2050), "soin", cared, "stable", held_word, "dit", said)


if __name__ == "__main__":
    main()
