"""Textes du jeu. Tout le contenu éditable est dans contenu.json.

Les valeurs des crans et leur affichage restent ici : ce sont les équations,
pas des phrases. Sans contenu.json, le jeu ne démarre pas.
"""

import json
import math
import random
from pathlib import Path

from .sim import (
    ALIC,
    CUF_WAR,
    FCEST,
    FOYERS,
    FX_NEUTRAL,
    IA_ICOR,
    ICOR,
    LAW_IDS,
    LYF,
    NRUF,
    PARTAGE,
    PPGF,
    START_YEAR,
    TURN_YEARS,
    YEAR_MAX,
    configure_kinds,
)


def _fmt_num(value):
    return f"{value:.1f}"


def _fmt_int(value):
    return f"{int(value)}"


def _fmt_pct(value):
    return f"{int(round(value * 100))}%"


def _fmt_school(value):
    return "NON" if value >= 3000 else f"{int(value)}"


def _fmt_ia(value):
    return f"X{1 / value:.1f}"


# Lien entre un mécanisme et les tables de sim.py. Le texte vient du fichier.
KIND_BIND = {
    "foyers": {"series": "pop", "values": FOYERS, "fmt": _fmt_num},
    "ateliers": {"series": "iopc", "values": ALIC, "fmt": _fmt_int},
    "terres": {"series": "fpc", "values": LYF, "fmt": _fmt_num},
    "rejets": {"series": "ppolx", "values": PPGF, "fmt": _fmt_pct},
    "filons": {"series": "nrfr", "values": NRUF, "fmt": _fmt_pct},
    "ecoles": {"series": "pop", "values": FCEST, "fmt": _fmt_school},
    "partage": {"series": "pop", "values": PARTAGE, "fmt": _fmt_pct},
    "technique": {"series": "iopc", "values": ICOR, "fmt": _fmt_num},
    "conflits": {"series": "iopc", "values": CUF_WAR, "fmt": _fmt_pct},
    "ia": {"series": "iopc", "values": IA_ICOR, "fmt": _fmt_ia},
}

CONTENU_PATH = Path(__file__).resolve().parent.parent / "contenu.json"

LAWS = []
INTRO = ()
AIDE = ()
INFO = ()
FIN = {}
EVENTS = ()
FORKS = {}
ISS_CARD = {}
SHOCKS = ()
EFFECTS = ()
SHOCK_BY_ID = {}
MECHANICS = {}
FX_HELP = ()
THEME_HELP = ()
_TEMPLATES = {}


def token_word(count):
    return "JETON" if int(count) <= 1 else "JETONS"


def token_label(count):
    return f"{int(count)} {token_word(count)}"


TABS = (
    ("monde", "MONDE"),
    ("lois", "ORIENTATIONS"),
    ("courbes", "COURBES"),
    ("temps", "RÉGLAGES"),
)


def pressure(sample):
    """La limite qui serre, dans l'ordre des scenarios du rapport."""
    pol = sample["ppolx"]
    food = sample["fpc"]
    metal = sample["nrfr"]
    goods = sample["iopc"]
    if pol >= 12.0 and (metal >= 0.34 or pol >= 15.0):
        return "pollution"
    if goods >= 380 and metal >= 0.40 and food >= 380 and pol < 12.0:
        return "essor"
    if food < 340 and metal >= 0.36 and pol < 11.0:
        return "sol"
    if metal < 0.28 and goods < 240:
        return "metal"
    if food < 340:
        return "faim"
    return "calme"


def resolve_event(ev, sample, notches):
    """La carte parle de la limite qui serre, pas seulement de son annee."""
    del notches
    kind = pressure(sample)
    if kind == "calme" or kind == ev.get("theme"):
        return ev
    fork = FORKS.get(kind)
    if not fork:
        return ev
    shown = dict(ev)
    shown.update(fork)
    return shown


def choice_parts(choice):
    label, index, delta, sub = choice[:4]
    shock = choice[4] if len(choice) > 4 else None
    return label, index, delta, sub, shock


def _fx(**kw):
    fx = dict(FX_NEUTRAL)
    fx.update(kw)
    return fx


# Ancien tirage, un choc par tour. Le jeu place maintenant les evenements
# Environ deux evenements tous les dix ans, jamais plus de trois entre deux conseils.
# roll_shock reste pour les tests.
SHOCK_CHANCE = 0.40
# Ecart moyen entre deux evenements, en annees.
# Sur les dix ans d'un conseil, les bords du tirage en mangent un peu :
# 4,6 ans d'ecart donnent environ deux cartes.
EVENT_EVERY = 4.6
EVENT_CAP = 3
HORIZON_CAP = 2200


def iss_visible(shocks, year):
    """La station est là tant que le choix de la lâcher n'est pas passé."""
    _label, _index, _delta, _sub, shock = choice_parts(ISS_CARD["b"])
    if not shock:
        return True
    year = float(year)
    for when, sid in shocks:
        if sid == shock and float(when) <= year + 1e-6:
            return False
    return True


def shock_banner(shocks, year):
    """La phrase d'un evenement tombe encore, douze ans apres."""
    best = None
    year = float(year)
    for when, sid in shocks:
        if when <= year + 1e-6 and year - when <= 12 and sid in SHOCK_BY_ID:
            if best is None or when > best[0]:
                best = (when, sid)
    if best is None:
        return None
    return SHOCK_BY_ID[best[1]]["banner"]


def roll_shock(seed, start, end, seen):
    """Un evenement inedit dans (start, end], ou None.

    Le tirage ne depend que de la graine, de l'annee et des evenements deja
    tombes : recharger la partie avant la carte redonne le meme.
    """
    seen = set(seen)
    pool = [s for s in SHOCKS if s["id"] not in seen]
    if not pool or float(end) <= float(start) + 0.3:
        return None
    token = f"{int(seed) & 0x7FFFFFFF}:{round(float(start), 3)}:{','.join(sorted(seen))}"
    rng = random.Random(token)
    if rng.random() >= SHOCK_CHANCE:
        return None
    pick = pool[rng.randrange(len(pool))]
    span = float(end) - float(start)
    year = float(start) + span * (0.30 + 0.55 * rng.random())
    for ev in EVENTS:
        cy = float(ev["year"])
        if abs(year - cy) < 0.45:
            year = cy + 0.7 if year >= cy else cy - 0.7
    year = min(float(end), max(float(start) + 0.2, year))
    return (round(year, 3), pick["id"])


TURN_LABEL = f"{TURN_YEARS} ANS"

def card_info(card):
    if not card:
        return ()
    info = card.get("info") or ()
    return tuple(str(line) for line in info if str(line).strip())


def next_stop(year, horizon):
    """Prochain conseil, ou la fin si l'horizon arrive avant."""
    year = float(year)
    horizon = float(horizon)
    if year >= horizon - 0.01:
        return ("fin", horizon)
    n = int(math.floor(year)) + 1
    while n % TURN_YEARS != 0:
        n += 1
    if n < 2030:
        n = 2030
    if n >= horizon - 0.01:
        return ("fin", horizon)
    return ("conseil", float(n))


def gap_floor(end):
    """Conseil, ou l'annee de depart, qui ouvre l'intervalle menant a `end`."""
    end_i = int(math.floor(float(end) + 1e-9))
    if end_i % TURN_YEARS == 0:
        prev = end_i - TURN_YEARS
    else:
        prev = end_i - (end_i % TURN_YEARS)
    return float(max(START_YEAR, prev))


def gap_event_count(shocks, end):
    """Cartes deja tombees depuis le conseil precedent, avant `end`."""
    lo = gap_floor(end)
    hi = float(end)
    return sum(1 for year, _sid in shocks if lo < float(year) < hi - 0.05)


def plan_events(seed, start, end, seen, before=0):
    """Evenements inedits dans (start, end), environ deux tous les dix ans.

    Jamais plus de trois entre deux conseils. `before` compte celles deja
    tombees dans le meme intervalle (reprise de partie).
    Ils tombent sur une annee entiere, jamais sur l'annee d'arrivee.
    Le tirage ne depend que de la graine, des bornes et des evenements deja tombes.
    """
    seen = set(seen)
    pool = [s["id"] for s in SHOCKS if s["id"] not in seen]
    start = float(start)
    end = float(end)
    if not pool or end <= start + 0.5:
        return []
    room = None
    if end - start <= float(TURN_YEARS) + 0.05:
        room = max(0, EVENT_CAP - max(0, int(before)))
    token = (
        f"{int(seed) & 0x7FFFFFFF}:{round(start, 3)}:{round(end, 3)}:"
        f"{','.join(sorted(seen))}"
    )
    rng = random.Random(token)
    out = []
    t = start
    limit = end - 0.5
    while pool and t < limit:
        if room is not None and len(out) >= room:
            break
        gap = max(1.0, -EVENT_EVERY * math.log(max(1e-9, 1.0 - rng.random())))
        t += gap
        if t >= limit:
            break
        year = float(round(t))
        if year <= start + 0.2 or year >= end - 0.2:
            continue
        if any(abs(year - y) < 0.5 for y, _sid in out):
            continue
        out.append((year, pool.pop(rng.randrange(len(pool)))))
    out.sort()
    return out


def dilemma_at(year, sample, notches, done):
    """Le dilemme du conseil, ou une fourche si la liste datee est finie."""
    done = set(done)
    year = int(round(float(year)))
    for ev in EVENTS:
        if ev.get("aside") or int(ev["year"]) != year or ev["id"] in done:
            continue
        return resolve_event(ev, sample, notches)
    kind = pressure(sample)
    if kind not in FORKS:
        kind = "essor"
    fork = FORKS[kind]
    shown = dict(fork)
    shown["id"] = f"suite-{year}-{kind}"
    shown["year"] = year
    shown["theme"] = kind
    return shown


def _choice_out(choice):
    label, index, delta, sub, shock = choice_parts(choice)
    return {
        "label": label,
        "law": index,
        "delta": int(delta or 0),
        "sub": sub,
        "shock": shock,
    }


def _choice_in(raw):
    if isinstance(raw, (list, tuple)):
        return tuple(raw)
    label = str((raw or {}).get("label") or "...").strip() or "..."
    law = (raw or {}).get("law")
    if law is None or law == "":
        law = None
    else:
        law = max(0, min(len(LAWS) - 1, int(law)))
    delta = int((raw or {}).get("delta") or 0)
    sub = str((raw or {}).get("sub") or "")
    shock = (raw or {}).get("shock") or None
    if shock:
        return (label, law, delta, sub, str(shock))
    return (label, law, delta, sub)


def _lines_in(raw, fallback=()):
    if raw is None:
        return tuple(fallback)
    if isinstance(raw, str):
        raw = [line.strip() for line in raw.splitlines() if line.strip()]
    return tuple(str(line) for line in raw)


def _reindex():
    global SHOCK_BY_ID
    SHOCK_BY_ID = {s["id"]: s for s in list(SHOCKS) + list(EFFECTS)}


def _note_list(raw):
    notes = []
    for level in raw or []:
        if isinstance(level, dict):
            notes.append(str(level.get("note") or ""))
        else:
            notes.append(str(level))
    return tuple(notes)


def _rebuild_templates():
    global _TEMPLATES
    _TEMPLATES = {}
    for kind, meta in MECHANICS.items():
        bind = KIND_BIND.get(kind)
        if bind is None:
            continue
        _TEMPLATES[kind] = {
            "kind": kind,
            "title": meta["title"],
            "series": bind["series"],
            "hint": tuple(meta["hint"]),
            "unit": meta["unit"],
            "values": bind["values"],
            "fmt": bind["fmt"],
            "up": meta["up"],
            "down": meta["down"],
            "info": tuple(meta["info"]),
            "level_notes": tuple(meta["levels"]),
        }


def _apply_mechanics(raw_list):
    global MECHANICS
    if not isinstance(raw_list, list) or not raw_list:
        return
    built = {}
    for raw in raw_list:
        if not isinstance(raw, dict):
            continue
        kind = str(raw.get("id") or "").strip()
        if kind not in KIND_BIND:
            continue
        hint = raw.get("hint") if isinstance(raw.get("hint"), list) else []
        built[kind] = {
            "title": str(raw.get("title") or kind),
            "unit": str(raw.get("unit") or ""),
            "hint": tuple(str(line) for line in hint),
            "up": str(raw.get("up") or ""),
            "down": str(raw.get("down") or ""),
            "info": _lines_in(raw.get("info")),
            "curve": str(raw.get("curve") or ""),
            "variable": str(raw.get("variable") or ""),
            "summary": str(raw.get("summary") or ""),
            "raise_effect": str(raw.get("raise_effect") or ""),
            "lower_effect": str(raw.get("lower_effect") or ""),
            "stack": str(raw.get("stack") or ""),
            "levels": _note_list(raw.get("levels")),
        }
    if not built:
        return
    MECHANICS = built
    _rebuild_templates()


def _apply_fx_help(raw_list):
    global FX_HELP
    if not isinstance(raw_list, list) or not raw_list:
        return
    rows = []
    for item in raw_list:
        if not isinstance(item, dict) or not str(item.get("key") or "").strip():
            continue
        rows.append(
            {
                "key": str(item["key"]),
                "group": str(item.get("group") or ""),
                "label": str(item.get("label") or ""),
                "neutral": float(item.get("neutral") or 0),
                "mode": str(item.get("mode") or ""),
                "effect": str(item.get("effect") or ""),
            }
        )
    if rows:
        FX_HELP = tuple(rows)


def _apply_themes(raw_list):
    global THEME_HELP
    if not isinstance(raw_list, list) or not raw_list:
        return
    rows = []
    for item in raw_list:
        if not isinstance(item, dict) or not str(item.get("id") or "").strip():
            continue
        rows.append(
            {
                "id": str(item["id"]),
                "label": str(item.get("label") or ""),
                "effect": str(item.get("effect") or ""),
            }
        )
    if rows:
        THEME_HELP = tuple(rows)


def _unique_law_id(preferred, kind, used):
    ident = str(preferred or "").strip() or kind
    if ident not in used:
        used.add(ident)
        return ident
    base = kind or ident
    n = 2
    while f"{base}-{n}" in used:
        n += 1
    ident = f"{base}-{n}"
    used.add(ident)
    return ident


def _law_from_raw(raw, used):
    if not isinstance(raw, dict):
        return None
    kind = str(raw.get("kind") or raw.get("id") or "").strip()
    template = _TEMPLATES.get(kind)
    if template is None:
        return None
    law = dict(template)
    law["kind"] = kind
    law["hint"] = tuple(template["hint"])
    law["info"] = tuple(template.get("info") or ())
    law["level_notes"] = tuple(template.get("level_notes") or ())
    law["id"] = _unique_law_id(raw.get("id"), kind, used)
    if "title" in raw:
        law["title"] = str(raw.get("title") or "").strip() or template["title"]
    hint = raw.get("hint")
    if isinstance(hint, list) and hint:
        pair = [str(line) for line in hint[:2]]
        while len(pair) < 2:
            pair.append("")
        law["hint"] = tuple(pair)
    if "unit" in raw:
        law["unit"] = str(raw.get("unit") or "")
    if "up" in raw:
        law["up"] = str(raw.get("up") or "")
    if "down" in raw:
        law["down"] = str(raw.get("down") or "")
    if isinstance(raw.get("info"), list):
        law["info"] = _lines_in(raw["info"])
    if isinstance(raw.get("levels"), list) and raw["levels"]:
        law["level_notes"] = _note_list(raw["levels"])
    series = str(raw.get("series") or "").strip() if "series" in raw else ""
    if series:
        law["series"] = series
    return law


def _apply_orientations(raw_list):
    if not isinstance(raw_list, list) or not raw_list:
        return
    used = set()
    built = []
    for raw in raw_list:
        law = _law_from_raw(raw, used)
        if law is not None:
            built.append(law)
    if not built:
        return
    LAWS.clear()
    LAWS.extend(built)
    configure_kinds([law["kind"] for law in LAWS])


def _levels_out(law):
    notes = list(law.get("level_notes") or MECHANICS.get(law["kind"], {}).get("levels") or ())
    out = []
    for index, value in enumerate(law["values"]):
        note = notes[index] if index < len(notes) else ""
        out.append({"shown": law["fmt"](value), "note": note})
    return out


def _orientation_out(law):
    return {
        "id": law.get("id") or law.get("kind"),
        "kind": law.get("kind"),
        "title": law["title"],
        "hint": list(law["hint"]),
        "unit": law["unit"],
        "up": law["up"],
        "down": law["down"],
        "info": list(law.get("info") or ()),
        "series": law.get("series") or "",
        "levels": _levels_out(law),
    }


def _mechanics_public():
    rows = []
    for kind in LAW_IDS:
        meta = MECHANICS.get(kind)
        bind = KIND_BIND.get(kind)
        if not meta or not bind:
            continue
        notes = list(meta["levels"])
        rows.append(
            {
                "id": kind,
                "title": meta["title"],
                "unit": meta["unit"],
                "hint": list(meta["hint"]),
                "up": meta["up"],
                "down": meta["down"],
                "info": list(meta.get("info") or ()),
                "curve": meta["curve"],
                "variable": meta["variable"],
                "summary": meta["summary"],
                "raise_effect": meta["raise_effect"],
                "lower_effect": meta["lower_effect"],
                "stack": meta["stack"],
                "levels": [
                    {"shown": bind["fmt"](value), "note": notes[index] if index < len(notes) else ""}
                    for index, value in enumerate(bind["values"])
                ],
            }
        )
    return rows


def document():
    """L'etat editable, pour l'editeur."""
    def pack_dilemma(ev):
        row = {
            "id": ev["id"],
            "year": int(ev.get("year") or 0),
            "theme": ev.get("theme") or "",
            "live_only": bool(ev.get("live_only")),
            "title": ev["title"],
            "lines": list(ev["lines"]),
            "info": list(ev.get("info") or ()),
            "a": _choice_out(ev["a"]),
            "b": _choice_out(ev["b"]),
        }
        if ev.get("aside"):
            row["aside"] = True
        return row

    orientations = [_orientation_out(law) for law in LAWS]
    dilemmas = [pack_dilemma(ev) for ev in EVENTS]
    dilemmas.append(pack_dilemma(ISS_CARD))
    forks = []
    for key, fork in FORKS.items():
        forks.append(
            {
                "id": key,
                "title": fork["title"],
                "lines": list(fork["lines"]),
                "info": list(fork.get("info") or ()),
                "a": _choice_out(fork["a"]),
                "b": _choice_out(fork["b"]),
            }
        )

    def pack_event(card, pool):
        return {
            "id": card["id"],
            "pool": pool,
            "title": card["title"],
            "lines": list(card["lines"]),
            "effect": card.get("effect") or "",
            "banner": card.get("banner") or "",
            "info": list(card.get("info") or ()),
            "fx": dict(card.get("fx") or {}),
        }

    return {
        "intro": [{"title": title, "lines": list(lines)} for title, lines in INTRO],
        "aide": list(AIDE),
        "credits": list(INFO),
        "fin": {
            key: {"title": title, "lines": list(lines)}
            for key, (title, lines) in FIN.items()
        },
        "mechanics": _mechanics_public(),
        "fx_help": [dict(row) for row in FX_HELP],
        "themes": [dict(row) for row in THEME_HELP],
        "orientations": orientations,
        "dilemmas": dilemmas,
        "forks": forks,
        "events": [pack_event(card, True) for card in SHOCKS]
        + [pack_event(card, False) for card in EFFECTS],
    }


def apply_document(doc):
    """Remplace les textes et les cartes. Chaque orientation garde les équations de son mécanisme."""
    global INTRO, AIDE, INFO, FIN, EVENTS, FORKS, SHOCKS, EFFECTS, ISS_CARD
    if not isinstance(doc, dict):
        return
    _apply_mechanics(doc.get("mechanics"))
    _apply_fx_help(doc.get("fx_help"))
    _apply_themes(doc.get("themes"))
    intro = []
    for slide in doc.get("intro") or []:
        title = str(slide.get("title") or "").strip() or "..."
        intro.append((title, _lines_in(slide.get("lines"), ("...",))))
    if intro:
        INTRO = tuple(intro)
    if isinstance(doc.get("aide"), list) and doc["aide"]:
        AIDE = tuple(str(line) for line in doc["aide"])
    if isinstance(doc.get("credits"), list) and doc["credits"]:
        INFO = tuple(str(line) for line in doc["credits"])
    fin = doc.get("fin") or {}
    if isinstance(fin, dict) and fin:
        merged = dict(FIN)
        for key, block in fin.items():
            if not isinstance(block, dict):
                continue
            title = str(block.get("title") or merged.get(key, ("...", ()))[0])
            lines = _lines_in(block.get("lines"), merged.get(key, ("", ()))[1])
            merged[str(key)] = (title, lines)
        FIN = merged
    _apply_orientations(doc.get("orientations"))
    dilemmas = []
    aside = None
    for raw in doc.get("dilemmas") or []:
        ident = str(raw.get("id") or "").strip()
        if not ident:
            continue
        card = {
            "id": ident,
            "year": int(raw.get("year") or 0),
            "theme": str(raw.get("theme") or ""),
            "live_only": bool(raw.get("live_only")),
            "title": str(raw.get("title") or ident),
            "lines": _lines_in(raw.get("lines"), ("...",)),
            "info": _lines_in(raw.get("info")),
            "a": _choice_in(raw.get("a")),
            "b": _choice_in(raw.get("b")),
        }
        if raw.get("aside") or ident == "iss":
            card["aside"] = True
            aside = card
            continue
        dilemmas.append(card)
    if dilemmas:
        EVENTS = tuple(dilemmas)
    if aside:
        ISS_CARD = aside
    forks = {}
    for raw in doc.get("forks") or []:
        ident = str(raw.get("id") or "").strip()
        if not ident:
            continue
        forks[ident] = {
            "title": str(raw.get("title") or ident),
            "lines": _lines_in(raw.get("lines"), ("...",)),
            "info": _lines_in(raw.get("info")),
            "a": _choice_in(raw.get("a")),
            "b": _choice_in(raw.get("b")),
        }
    if forks:
        FORKS = forks
    shocks = []
    effects = []
    for raw in doc.get("events") or []:
        ident = str(raw.get("id") or "").strip()
        if not ident:
            continue
        fx = raw.get("fx") if isinstance(raw.get("fx"), dict) else {}
        card = {
            "id": ident,
            "title": str(raw.get("title") or ident),
            "lines": _lines_in(raw.get("lines"), ("...",)),
            "effect": str(raw.get("effect") or ""),
            "banner": str(raw.get("banner") or ""),
            "info": _lines_in(raw.get("info")),
            "fx": _fx(**{k: float(v) for k, v in fx.items() if k in _fx()}),
        }
        if raw.get("pool", True):
            shocks.append(card)
        else:
            effects.append(card)
    if shocks or effects:
        SHOCKS = tuple(shocks)
        EFFECTS = tuple(effects)
        _reindex()


def load_contenu(path=None):
    path = Path(path) if path else CONTENU_PATH
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"contenu illisible : {path}") from exc
    apply_document(doc)
    return True


def save_contenu(doc, path=None):
    path = Path(path) if path else CONTENU_PATH
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    apply_document(doc)


load_contenu()
