"""World3, pilote par une suite de decisions datees.

Le passe (1900 jusqu'au premier cran du joueur) reste le scenario standard.
Chaque cran ajoute une politique a partir de son annee. Relancer le modele
reconstruit toute la trajectoire : l'histoire d'avant le cran ne bouge pas,
l'avenir si.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from pyworld3 import World3

START_YEAR = 2026
YEAR_MIN = 1900
YEAR_MAX = 2100
TURN_YEARS = 10

# Dix crans. L'index 0 est le scenario historique.
# En 2026 le monde standard est deja au pic : ces crans ne rewindent pas
# le passe, ils changent la texture de la chute ou de la tenue.
FOYERS = (4.0, 3.5, 3.0, 2.5, 2.0)           # dcfsn, une norme. Le cran 4 plafonne le souhait a 2
ALIC = (14.0, 17.0, 20.0, 24.0, 28.0)       # duree de vie du capital, en annees
TENIR = (0.0, 0.25, 0.50, 0.75, 1.0)        # part du cran Usines qui cesse d'ajouter du capital
LYF = (1.0, 1.1, 1.2, 1.6, 2.0)              # rendement des terres
PPGF = (1.0, 0.80, 0.55, 0.35, 0.22)        # pollution generee par unite
NRUF = (1.0, 0.80, 0.60, 0.45, 0.30)        # ressources consommees par personne
FCEST = (4000.0, 2080.0, 2060.0, 2040.0, 2026.0)  # annee ou l'instruction agit
PARTAGE = (0.0, 0.05, 0.09, 0.14, 0.18)     # part retiree aux usines neuves
ICOR = (3.0, 2.7, 2.4, 2.1, 1.8)            # capital par unite produite
CUF_WAR = (1.0, 0.95, 0.88, 0.78, 0.65)     # part du capital encore au travail
IA_ICOR = (1.0, 0.92, 0.84, 0.76, 0.68)     # multiplicateur, s'ajoute a la technique
IA_LOAD = (1.0, 1.08, 1.18, 1.30, 1.45)     # ressources et pollution en plus
SATELLITES = (8, 16, 28, 44, 64)

# Inertie. Un cran pose une cible ; le parametre y va en ligne droite sur ce
# nombre d'annees, depuis la valeur effective au moment du conseil. Les
# machines se renouvellent, une norme se diffuse : rien ne bascule l'annee meme.
RAMP_YEARS = {
    "dcfsn": 12.0,     # une norme de famille change sur une demi-generation
    "alic": 10.0,      # le parc de machines se renouvelle
    "tenir": 10.0,
    "lyf": 10.0,       # diffusion des pratiques agricoles
    "ppgf": 12.0,      # renouvellement des procedes
    "nruf": 12.0,
    "fcest": 0.0,      # une date, pas une intensite
    "partage": 5.0,    # un budget se reoriente vite
    "icor": 12.0,      # le capital neuf porte la technique
    "cuf": 4.0,        # un conflit detourne le capital vite
    "ia_icor": 8.0,    # diffusion d'une technique logicielle
    "ia_load": 8.0,
    "lock": 12.0,      # plafond a deux enfants, comme la norme
}

# Multiplicateurs neutres d'un evenement. `ramp` est la duree, en annees, de
# la montee en puissance (0 : effet plein l'annee meme). `fcaor_add` ajoute
# une part du capital industriel detournee vers l'extraction.
FX_NEUTRAL = {
    "lyf": 1.0,
    "ppgf": 1.0,
    "nruf": 1.0,
    "alic": 1.0,
    "icor": 1.0,
    "cuf": 1.0,
    "dcfs": 1.0,
    "mort": 1.0,
    "fcaor_add": 0.0,
    "pop_keep": 1.0,
    "nr_keep": 1.0,
    "al_keep": 1.0,
    "ic_keep": 1.0,
    "ppolx_add": 0.0,
    "nri_add": 0.0,
    "ramp": 0.0,
}
# Durables, en multiplicateur : montent de 1 vers la valeur pendant `ramp`.
# Les autres (pop_keep, nr_keep, al_keep, ic_keep, ppolx_add) sont des chocs
# de stock, une seule fois l'annee du franchissement ; nri_add suit `ramp`.
FX_DURABLE = ("lyf", "ppgf", "nruf", "alic", "icor", "cuf", "dcfs", "mort")

LAW_IDS = (
    "foyers",
    "ateliers",
    "terres",
    "rejets",
    "filons",
    "ecoles",
    "partage",
    "technique",
    "conflits",
    "ia",
)
# L'editeur peut retirer ou dupliquer un levier. L'ordre est celui du cadran.
LAW_COUNT = len(LAW_IDS)
_ACTIVE_KINDS = list(LAW_IDS)

SCALES = {
    "pop": 8e9,
    "fpc": 1000.0,
    "iopc": 500.0,
    "ppolx": 16.0,
    "nrfr": 1.0,
}

UNITS = {
    "pop": "MD",
    "fpc": "KG",
    "iopc": "",
    "ppolx": "",
    "nrfr": "%",
}


def law_count() -> int:
    return LAW_COUNT


def active_kinds() -> tuple:
    return tuple(_ACTIVE_KINDS)


def pad_notches(notches) -> tuple:
    clean = tuple(max(0, min(4, int(n))) for n in notches)
    if len(clean) < LAW_COUNT:
        clean = clean + (0,) * (LAW_COUNT - len(clean))
    return clean[:LAW_COUNT]


def notch_for(notches, kind: str) -> int:
    """Cran retenu pour un mecanisme. S'il y en a plusieurs, le plus haut l'emporte."""
    best = 0
    padded = pad_notches(notches)
    for index, name in enumerate(_ACTIVE_KINDS):
        if name == kind:
            best = max(best, padded[index])
    return best


@dataclass(frozen=True)
class Policy:
    dcfsn: float
    alic: float
    tenir: float
    lyf: float
    ppgf: float
    nruf: float
    fcest: float
    partage: float
    icor: float
    cuf: float
    ia_icor: float
    ia_load: float
    pop_lock: bool


def policy_from(notches) -> Policy:
    a = notch_for(notches, "foyers")
    b = notch_for(notches, "ateliers")
    c = notch_for(notches, "terres")
    d = notch_for(notches, "rejets")
    e = notch_for(notches, "filons")
    f = notch_for(notches, "ecoles")
    g = notch_for(notches, "partage")
    h = notch_for(notches, "technique")
    i = notch_for(notches, "conflits")
    j = notch_for(notches, "ia")
    return Policy(
        FOYERS[a],
        ALIC[b],
        TENIR[b],
        LYF[c],
        PPGF[d],
        NRUF[e],
        FCEST[f],
        PARTAGE[g],
        ICOR[h],
        CUF_WAR[i],
        IA_ICOR[j],
        IA_LOAD[j],
        a >= 4,
    )


def baseline_schedule():
    return ((float(YEAR_MIN), (0,) * LAW_COUNT),)


def satellite_count(notches) -> int:
    return SATELLITES[notch_for(notches, "technique")]


class StewardsWorld(World3):
    """World3 dont les crans suivent un calendrier.

    Les evenements (shocks) s'ajoutent a partir de leur annee : un
    multiplicateur qui dure, monte en puissance sur `ramp` annees, ou un
    cran unique sur un stock (gens, metal, terres, usines, pollution). Le
    metal decouvert (`nri_add`) arrive etale sur `ramp` annees.

    Les crans, eux, ont une inertie : chaque parametre glisse en ligne
    droite de sa valeur effective au conseil vers la cible, en RAMP_YEARS.
    """

    def __init__(self, schedule, shocks=(), year_max=YEAR_MAX):
        super().__init__(
            year_min=YEAR_MIN,
            year_max=int(year_max),
            dt=1,
            pyear=1975,
            verbose=False,
        )
        self._years = tuple(float(year) for year, _ in schedule)
        self._policies = tuple(policy_from(notches) for _, notches in schedule)
        self._starts = self._ramp_starts()
        self._shocks = tuple((float(year), str(sid)) for year, sid in shocks)
        self._shock_fx = None
        self._pol_cache = {}

    def _catalog(self):
        if self._shock_fx is None:
            from .content import SHOCK_BY_ID

            self._shock_fx = SHOCK_BY_ID
        return self._shock_fx

    def _shock_fx_list(self):
        """(annee, fx) des evenements dont la fiche existe."""
        catalog = self._catalog()
        out = []
        for year, sid in self._shocks:
            fx = catalog.get(sid, {}).get("fx")
            if fx:
                out.append((year, fx))
        return out

    @staticmethod
    def _ramp_u(t, year, ramp) -> float:
        """Part de l'effet atteinte a `t` : 1 des l'annee si ramp vaut 0."""
        if ramp <= 0.0:
            return 1.0
        return max(0.0, min(1.0, (float(t) - float(year)) / float(ramp)))

    def fx_at(self, t) -> dict:
        """Produit des multiplicateurs durables deja en cours, montee comprise."""
        out = None
        t = float(t)
        for year, fx in self._shock_fx_list():
            if year > t + 1e-6:
                continue
            u = self._ramp_u(t, year, fx.get("ramp", 0.0))
            if out is None:
                out = dict(FX_NEUTRAL)
            for key in FX_DURABLE:
                value = float(fx.get(key, 1.0))
                if value != 1.0:
                    out[key] *= 1.0 + (value - 1.0) * u
            out["fcaor_add"] += float(fx.get("fcaor_add", 0.0)) * u
        return out

    def oneshot(self, t_prev, t_now):
        """Chocs de stock franchis entre deux pas. Identite s'il n'y en a pas."""
        pop = nr = al = ic = 1.0
        ppol = 0.0
        hit = False
        t_prev = float(t_prev)
        t_now = float(t_now)
        for year, fx in self._shock_fx_list():
            if not (t_prev < year <= t_now + 1e-9):
                continue
            hit = True
            pop *= fx["pop_keep"]
            nr *= fx["nr_keep"]
            al *= fx["al_keep"]
            ic *= fx["ic_keep"]
            ppol += fx["ppolx_add"]
        if not hit:
            return None
        return pop, nr, al, ic, ppol

    def nri_drip(self, t_prev, t_now) -> float:
        """Fraction du stock d'origine decouverte entre deux pas.

        Sans `ramp`, tout tombe l'annee du franchissement. Avec, la part
        arrive au prorata des annees de montee comprises dans le pas.
        """
        total = 0.0
        t_prev = float(t_prev)
        t_now = float(t_now)
        for year, fx in self._shock_fx_list():
            add = float(fx.get("nri_add", 0.0))
            if not add:
                continue
            ramp = float(fx.get("ramp", 0.0))
            if ramp <= 0.0:
                if t_prev < year <= t_now + 1e-9:
                    total += add
                continue
            lo = max(t_prev, year)
            hi = min(t_now, year + ramp)
            if hi > lo:
                total += add * (hi - lo) / ramp
        return total

    @staticmethod
    def _scalar(pol: Policy, field: str) -> float:
        if field == "lock":
            return 1.0 if pol.pop_lock else 0.0
        return float(getattr(pol, field))

    def _ramp_starts(self):
        """Valeur effective de chaque parametre a l'ouverture de chaque cran."""
        starts = []
        for i, pol in enumerate(self._policies):
            if i == 0:
                starts.append({f: self._scalar(pol, f) for f in RAMP_YEARS})
                continue
            prev = {}
            year = self._years[i]
            for f in RAMP_YEARS:
                prev[f] = self._eff(i - 1, f, year, starts)
            starts.append(prev)
        return starts

    def _eff(self, idx, field, t, starts=None) -> float:
        starts = self._starts if starts is None else starts
        target = self._scalar(self._policies[idx], field)
        start = starts[idx][field]
        if start == target:
            return target
        u = self._ramp_u(t, self._years[idx], RAMP_YEARS[field])
        return start + (target - start) * u

    def _segment(self, t) -> int:
        idx = 0
        for i, year in enumerate(self._years):
            if year <= t + 1e-6:
                idx = i
            else:
                break
        return idx

    def policy_at(self, t) -> Policy:
        """Politique effective : les cibles du cran, atteintes avec inertie."""
        t = float(t)
        hit = self._pol_cache.get(t)
        if hit is not None:
            return hit
        idx = self._segment(t)
        target = self._policies[idx]
        pol = Policy(
            dcfsn=self._eff(idx, "dcfsn", t),
            alic=self._eff(idx, "alic", t),
            tenir=self._eff(idx, "tenir", t),
            lyf=self._eff(idx, "lyf", t),
            ppgf=self._eff(idx, "ppgf", t),
            nruf=self._eff(idx, "nruf", t),
            fcest=target.fcest,
            partage=self._eff(idx, "partage", t),
            icor=self._eff(idx, "icor", t),
            cuf=self._eff(idx, "cuf", t),
            ia_icor=self._eff(idx, "ia_icor", t),
            ia_load=self._eff(idx, "ia_load", t),
            pop_lock=target.pop_lock,
        )
        self._pol_cache[t] = pol
        return pol

    def lock_at(self, t) -> float:
        """Force du plafond a deux enfants, de 0 a 1, avec la meme inertie."""
        t = float(t)
        return self._eff(self._segment(t), "lock", t)

    def _base_nri(self) -> float:
        if getattr(self, "_nri0", None) is None:
            self._nri0 = float(self.nri)
        return self._nri0

    def _update_nruf(self, k):
        pol = self.policy_at(self.time[k])
        self.nruf[k] = pol.nruf * pol.ia_load
        fx = self.fx_at(self.time[k])
        if fx and fx["nruf"] != 1.0:
            self.nruf[k] = min(3.0, max(0.15, self.nruf[k] * fx["nruf"]))

    def _update_ppgf(self, k):
        pol = self.policy_at(self.time[k])
        self.ppgf[k] = pol.ppgf * pol.ia_load
        fx = self.fx_at(self.time[k])
        if fx and fx["ppgf"] != 1.0:
            self.ppgf[k] = min(3.0, max(0.20, self.ppgf[k] * fx["ppgf"]))

    def _update_lyf(self, k):
        self.lyf[k] = self.policy_at(self.time[k]).lyf
        fx = self.fx_at(self.time[k])
        if fx and fx["lyf"] != 1.0:
            self.lyf[k] = min(2.4, max(0.45, self.lyf[k] * fx["lyf"]))

    def _update_alic(self, k):
        self.alic[k] = self.policy_at(self.time[k]).alic
        fx = self.fx_at(self.time[k])
        if fx and fx["alic"] != 1.0:
            self.alic[k] = min(40.0, max(8.0, self.alic[k] * fx["alic"]))

    def _update_dcfs(self, k):
        pol = self.policy_at(self.time[k])
        dcfsn = pol.dcfsn
        fx = self.fx_at(self.time[k])
        if fx and fx["dcfs"] != 1.0:
            dcfsn = min(6.5, max(1.6, dcfsn * fx["dcfs"]))
        self.dcfsn = dcfsn
        # Le cran 4 est un plafond : le souhait ne repasse pas au-dessus de 2.
        # Les crans d'avant continuent de compter. zpgt, lui, remplacerait
        # le produit par 2, y compris quand la norme veut moins.
        # Le plafond s'installe avec la meme inertie que la norme.
        self.zpgt = 4000.0
        super()._update_dcfs(k)
        lock = self.lock_at(self.time[k])
        if lock > 0.0:
            want = float(self.dcfs[k])
            self.dcfs[k] = want - lock * max(0.0, want - 2.0)

    def _update_fce(self, k):
        self.fcest = self.policy_at(self.time[k]).fcest
        super()._update_fce(k)

    def _update_fcaor(self, k):
        # Le metal profond coute du capital : une part des usines creuse.
        super()._update_fcaor(k)
        fx = self.fx_at(self.time[k])
        if fx and fx["fcaor_add"]:
            self.fcaor[k] = min(0.95, float(self.fcaor[k]) + fx["fcaor_add"])

    def _update_icor(self, k):
        pol = self.policy_at(self.time[k])
        self.icor[k] = pol.icor * pol.ia_icor
        fx = self.fx_at(self.time[k])
        if fx and fx["icor"] != 1.0:
            self.icor[k] = min(6.0, max(0.90, self.icor[k] * fx["icor"]))

    def _update_cuf(self, k):
        super()._update_cuf(k)
        self.cuf[k] *= self.policy_at(self.time[k]).cuf
        fx = self.fx_at(self.time[k])
        if fx and fx["cuf"] != 1.0:
            self.cuf[k] = min(1.0, max(0.35, self.cuf[k] * fx["cuf"]))

    def _update_d1(self, k, kl):
        super()._update_d1(k, kl)
        self._scale_death(k, "d1", kl)

    def _update_d2(self, k, kl):
        super()._update_d2(k, kl)
        self._scale_death(k, "d2", kl)

    def _update_d3(self, k, kl):
        super()._update_d3(k, kl)
        self._scale_death(k, "d3", kl)

    def _update_d4(self, k, kl):
        super()._update_d4(k, kl)
        self._scale_death(k, "d4", kl)

    def _scale_death(self, k, name, kl):
        fx = self.fx_at(self.time[k])
        if fx and fx["mort"] != 1.0:
            series = getattr(self, name)
            series[kl] *= min(1.5, max(0.55, fx["mort"]))

    def _update_state_p1(self, k, j, jk):
        super()._update_state_p1(k, j, jk)
        self._apply_pop(k, j, "p1")

    def _update_state_p2(self, k, j, jk):
        super()._update_state_p2(k, j, jk)
        self._apply_pop(k, j, "p2")

    def _update_state_p3(self, k, j, jk):
        super()._update_state_p3(k, j, jk)
        self._apply_pop(k, j, "p3")

    def _update_state_p4(self, k, j, jk):
        super()._update_state_p4(k, j, jk)
        self._apply_pop(k, j, "p4")

    def _hit(self, k, j):
        if k <= 0:
            return None
        return self.oneshot(self.time[j], self.time[k])

    def _apply_pop(self, k, j, name):
        hit = self._hit(k, j)
        if hit and hit[0] != 1.0:
            series = getattr(self, name)
            series[k] *= hit[0]

    def _update_state_nr(self, k, j, jk):
        super()._update_state_nr(k, j, jk)
        hit = self._hit(k, j)
        if hit and hit[1] != 1.0:
            self.nr[k] = min(self.nri, max(0.0, self.nr[k] * hit[1]))
        if k <= 0:
            return
        drip = self.nri_drip(self.time[j], self.time[k])
        if drip:
            # Plus de metal exploitable, au rythme ou les mines ouvrent.
            extra = self._base_nri() * drip
            self.nri += extra
            self.nr[k] = min(self.nri, self.nr[k] + extra)

    def _update_state_al(self, k, j, jk):
        super()._update_state_al(k, j, jk)
        hit = self._hit(k, j)
        if hit and hit[2] != 1.0:
            self.al[k] *= hit[2]

    def _update_state_ic(self, k, j, jk):
        super()._update_state_ic(k, j, jk)
        hit = self._hit(k, j)
        if hit and hit[3] != 1.0:
            self.ic[k] *= hit[3]

    def _update_state_ppol(self, k, j, jk):
        super()._update_state_ppol(k, j, jk)
        hit = self._hit(k, j)
        if hit and hit[4]:
            self.ppol[k] += hit[4] * self.ppol70

    def _update_fioas(self, k):
        super()._update_fioas(k)
        shift = self.policy_at(self.time[k]).partage
        if shift:
            self.fioas[k] += shift * 0.5

    def _update_fioai(self, k):
        # Les soins prennent sur les usines neuves. La part des champs reste.
        pol = self.policy_at(self.time[k])
        shift = pol.partage
        if shift:
            half = shift * 0.5
            self.fioac[k] += half
            base_as = self.fioas[k] - half
            base_ac = self.fioac[k] - half
            room = 1.0 - self.fioaa[k] - base_as - base_ac
            extra = half * 2.0
            if extra > room:
                keep = max(0.0, room) / extra
                self.fioas[k] = base_as + half * keep
                self.fioac[k] = base_ac + half * keep
        super()._update_fioai(k)
        self._hold_capital(k, pol)

    def _hold_capital(self, k, pol):
        """Usines : on cesse d'ajouter du capital au-delà du remplacement."""
        tenir = pol.tenir
        if tenir <= 0.0:
            return
        io = float(self.io[k])
        if io <= 1.0:
            return
        current = max(0.0, float(self.fioai[k]))
        eq = float(self.ic[k]) / (io * float(self.alic[k]))
        eq = max(0.0, min(current, eq))
        target = (1.0 - tenir) * current + tenir * eq
        delta = current - target
        self.fioai[k] = target
        self.fioac[k] += delta


@dataclass
class Trajectory:
    time: np.ndarray
    pop: np.ndarray
    fpc: np.ndarray
    iopc: np.ndarray
    ppolx: np.ndarray
    nrfr: np.ndarray
    year_max: float = YEAR_MAX

    def _lerp(self, series, year: float) -> float:
        cap = float(self.year_max)
        year = float(np.clip(year, YEAR_MIN, cap))
        if year >= cap:
            return float(series[-1])
        x = year - YEAR_MIN
        i = int(x)
        f = x - i
        return float(series[i] * (1.0 - f) + series[i + 1] * f)

    def sample(self, year: float) -> dict:
        return {
            "pop": self._lerp(self.pop, year),
            "fpc": self._lerp(self.fpc, year),
            "iopc": self._lerp(self.iopc, year),
            "ppolx": self._lerp(self.ppolx, year),
            "nrfr": self._lerp(self.nrfr, year),
        }

    def column(self, key: str) -> np.ndarray:
        return getattr(self, key)


_CACHE: dict = {}
_CACHE_ORDER: list = []
# Un seul calcul à la fois, dans un autre processus : le jeu continue
# d'afficher et de lire le doigt pendant les deux secondes du modèle.
_PENDING: dict = {}
_QUEUE: list = []
_QUEUE_ARGS: dict = {}
# Choix encore à l'écran : on ne le chasse pas quand la file déborde.
_HOLD = None
_FAILED: set = set()
_POOL = None
_POOL_BROKEN = False
_CACHE_CAP = 24


def clear_cache():
    _CACHE.clear()
    _CACHE_ORDER.clear()


def configure_kinds(kinds) -> None:
    """Remplace les leviers du cadran. Un mecanisme absent reste au cran historique."""
    global LAW_COUNT
    known = set(LAW_IDS)
    clean = [str(kind) for kind in kinds if str(kind) in known]
    if not clean:
        clean = list(LAW_IDS)
    _ACTIVE_KINDS[:] = clean
    LAW_COUNT = len(_ACTIVE_KINDS)
    clear_cache()


def _schedule_key(schedule, shocks=(), year_max=YEAR_MAX):
    year_max = int(year_max)
    sched_key = tuple((round(float(y), 3), pad_notches(n)) for y, n in schedule)
    shock_key = tuple((round(float(y), 3), str(sid)) for y, sid in shocks)
    key = (tuple(_ACTIVE_KINDS), sched_key, shock_key, year_max)
    return key, sched_key, shock_key, year_max


def _store_traj(key, time, pop, fpc, iopc, ppolx, nrfr, year_max):
    traj = Trajectory(
        time=time, pop=pop, fpc=fpc, iopc=iopc, ppolx=ppolx, nrfr=nrfr,
        year_max=float(year_max),
    )
    _CACHE[key] = traj
    if key in _CACHE_ORDER:
        _CACHE_ORDER.remove(key)
    _CACHE_ORDER.append(key)
    while len(_CACHE_ORDER) > _CACHE_CAP:
        old = _CACHE_ORDER.pop(0)
        _CACHE.pop(old, None)
    return traj


def _drop_pool():
    """Le calculateur est mort. On l'oubliera et le prochain tour en ouvrira un."""
    global _POOL, _POOL_BROKEN
    pool = _POOL
    _POOL = None
    _POOL_BROKEN = False
    _PENDING.clear()
    if pool is None:
        return
    try:
        pool.shutdown(wait=False, cancel_futures=True)
    except Exception:
        pass


def _compute_arrays(kinds, sched_key, shock_key, year_max):
    """Tour du modèle, hors du processus qui dessine."""
    # Le contenu fixe les leviers à l'import. On les repose ensuite.
    from . import content  # noqa: F401

    configure_kinds(list(kinds))
    world = StewardsWorld(sched_key, shock_key, int(year_max))
    world.init_world3_constants()
    world.init_world3_variables()
    world.set_world3_table_functions()
    world.set_world3_delay_functions(method="euler")
    world.run_world3(fast=True)
    pop = np.array(world.pop, dtype=np.float64)
    if not np.isfinite(pop).all():
        raise RuntimeError("trajectoire non finie")
    return (
        np.array(world.time, dtype=np.float64),
        pop,
        np.array(world.fpc, dtype=np.float64),
        np.array(world.iopc, dtype=np.float64),
        np.array(world.ppolx, dtype=np.float64),
        np.array(world.nrfr, dtype=np.float64),
        float(year_max),
    )


def _pool():
    global _POOL, _POOL_BROKEN
    if _POOL_BROKEN:
        return None
    if _POOL is None:
        import multiprocessing as mp
        from concurrent.futures import ProcessPoolExecutor

        try:
            # spawn : le calcul n'hérite pas de l'écran. Le contexte du Pi
            # n'a pas ProcessPoolExecutor comme méthode.
            _POOL = ProcessPoolExecutor(
                max_workers=1, mp_context=mp.get_context("spawn"),
            )
        except Exception:
            _POOL_BROKEN = True
            return None
    return _POOL


def close_schedules():
    """Arrête le calcul en tâche de fond. Le jeu qui se ferme n'attend pas."""
    global _POOL, _HOLD
    pending = _POOL
    _POOL = None
    _HOLD = None
    _PENDING.clear()
    _QUEUE.clear()
    _QUEUE_ARGS.clear()
    if pending is not None:
        pending.shutdown(wait=False, cancel_futures=True)


def _pump():
    pool = _pool()
    if pool is None or _PENDING:
        return
    while _QUEUE:
        key = _QUEUE.pop(0)
        args = _QUEUE_ARGS.pop(key, None)
        if args is None or key in _CACHE:
            continue
        try:
            _PENDING[key] = pool.submit(_compute_arrays, *args)
        except Exception:
            _FAILED.add(key)
            continue
        return


def poll_schedules():
    """Range les trajectoires terminées. À appeler depuis la boucle du jeu."""
    if _PENDING:
        done = [key for key, fut in _PENDING.items() if fut.done()]
        for key in done:
            fut = _PENDING.pop(key)
            try:
                _store_traj(key, *fut.result())
                _FAILED.discard(key)
            except Exception:
                _FAILED.add(key)
                _drop_pool()
    _pump()


def warm_schedule(schedule, shocks=(), year_max=YEAR_MAX, front=False):
    """Lance le calcul sans bloquer l'image en cours.

    front place ce monde en tête. Le choix encore affiché ne reste pas
    derrière des trajectoires déjà quittées, et la file ne le chasse pas.
    """
    global _HOLD
    key, sched_key, shock_key, year_max = _schedule_key(schedule, shocks, year_max)
    if key in _CACHE or key in _PENDING:
        return
    if key in _QUEUE:
        if front and _QUEUE[0] != key:
            _QUEUE.remove(key)
            _QUEUE.insert(0, key)
    else:
        if front:
            _QUEUE.insert(0, key)
        else:
            _QUEUE.append(key)
        _QUEUE_ARGS[key] = (tuple(_ACTIVE_KINDS), sched_key, shock_key, year_max)
    if front:
        _HOLD = key
    while len(_QUEUE) > 6:
        if _HOLD is not None and _QUEUE and _QUEUE[0] == _HOLD and len(_QUEUE) > 1:
            dropped = _QUEUE.pop()
        else:
            dropped = _QUEUE.pop(0)
        _QUEUE_ARGS.pop(dropped, None)
        if dropped == _HOLD:
            _HOLD = None
    _pump()


def peek_schedule(schedule, shocks=(), year_max=YEAR_MAX):
    """La trajectoire si elle est prête. None tant que le calcul tourne."""
    poll_schedules()
    key, _sched, _shock, _year = _schedule_key(schedule, shocks, year_max)
    hit = _CACHE.get(key)
    if hit is not None:
        return hit
    if key in _FAILED:
        _FAILED.discard(key)
        return run_schedule(schedule, shocks, year_max)
    return None


def run_schedule(schedule, shocks=(), year_max=YEAR_MAX) -> Trajectory:
    """Simule de 1900 jusqu'a l'horizon. Le resultat est mis en cache."""
    key, sched_key, shock_key, year_max = _schedule_key(schedule, shocks, year_max)
    hit = _CACHE.get(key)
    if hit is not None:
        return hit

    world = StewardsWorld(sched_key, shock_key, year_max)
    world.init_world3_constants()
    world.init_world3_variables()
    world.set_world3_table_functions()
    world.set_world3_delay_functions(method="euler")
    world.run_world3(fast=True)

    pop = np.array(world.pop, dtype=np.float64)
    if not np.isfinite(pop).all():
        raise RuntimeError("trajectoire non finie")
    return _store_traj(
        key,
        np.array(world.time, dtype=np.float64),
        pop,
        np.array(world.fpc, dtype=np.float64),
        np.array(world.iopc, dtype=np.float64),
        np.array(world.ppolx, dtype=np.float64),
        np.array(world.nrfr, dtype=np.float64),
        float(year_max),
    )


def judge(now: dict, earlier: dict, year: float | None = None) -> str:
    """Un mot pour l'etat du monde, a partir des sorties reelles du modele.

    STABLE admet une descente lente, environ 1 % par an, tant que l'on
    mange, que l'industrie suit sans fondre, que l'air redescend et qu'il
    reste du metal. RALENTISSEMENT est une descente plus vive ou l'on mange
    encore. FAMINE est le scenario sans decision.
    """
    pop = max(earlier["pop"], 1.0)
    slope = (now["pop"] - earlier["pop"]) / pop / 5.0
    goods = max(earlier["iopc"], 1.0)
    goods_slope = (now["iopc"] - earlier["iopc"]) / goods / 5.0
    food_bad = now["fpc"] < 300
    food_low = now["fpc"] < 380
    food_ok = now["fpc"] >= 420
    goods_dead = now["iopc"] < 45
    goods_ok = now["iopc"] >= 130
    poison_hi = now["ppolx"] >= 10
    poison_mid = now["ppolx"] >= 6.0
    mines_lo = now["nrfr"] < 0.20
    mines_ok = now["nrfr"] >= 0.22

    if year is not None and year < 1990 and slope >= 0 and now["fpc"] >= 280 and now["ppolx"] < 8:
        return "CROISSANCE"
    if food_bad or (goods_dead and now["fpc"] < 400):
        return "FAMINE"
    # Hausse encore étroite. Descente lente admise : environ 1 % par an,
    # tant que l'on mange, que l'air et le métal tiennent, et que l'industrie
    # suit sans perdre plus de 1,2 % par an.
    if (
        food_ok
        and goods_ok
        and not poison_mid
        and mines_ok
        and -0.01 < slope < 0.0035
        and goods_slope > -0.012
    ):
        return "STABLE"
    if (
        food_ok
        and now["iopc"] >= 80
        and now["ppolx"] < 8
        and now["nrfr"] >= 0.18
        and slope > -0.016
    ):
        return "RALENTISSEMENT"
    if slope > 0.002 and now["fpc"] >= 380 and now["ppolx"] < 8:
        return "CROISSANCE"
    if poison_hi or mines_lo or food_low:
        return "CRISE"
    return "TENSION"


def format_vital(key: str, value: float) -> str:
    if key == "pop":
        return f"{value / 1e9:.2f}"
    if key == "fpc":
        return f"{value:.0f}"
    if key == "iopc":
        return f"{value:.0f}"
    if key == "ppolx":
        return f"{value:.1f}"
    return f"{value * 100:.0f}"


_MOVE = (
    ("fpc", "ON MANGE MOINS", "ON MANGE MIEUX"),
    ("ppolx", "MOINS DE POLLUTION", "PLUS DE POLLUTION"),
    ("nrfr", "MOINS DE MÉTAL", "PLUS DE MÉTAL"),
    ("pop", "MOINS DE GENS", "PLUS DE GENS"),
    ("iopc", "MOINS D'OBJETS", "PLUS D'OBJETS"),
)


def move_line(before: dict, after: dict) -> str:
    """La phrase du plus gros changement entre deux annees."""
    best = None
    best_mag = 0.012
    for key, down, up in _MOVE:
        mag = abs(after[key] - before[key]) / SCALES[key]
        if mag > best_mag:
            best_mag = mag
            best = down if after[key] < before[key] else up
    return best or "PRESQUE RIEN N'A BOUGÉ"


def talk_lines(now: dict, earlier: dict) -> list:
    """Ce que la planete dit, du plus urgent au simple mouvement."""
    lines = []
    if now["fpc"] < 300:
        lines.append("ON MANQUE À MANGER")
    elif now["fpc"] < 420:
        lines.append("ON MANGE JUSTE")
    if now["ppolx"] >= 10:
        lines.append("L'AIR EST TROP SALE")
    elif now["ppolx"] >= 6:
        lines.append("L'AIR EST LOURD")
    if now["nrfr"] < 0.20:
        lines.append("LES MINES SONT VIDES")
    elif now["nrfr"] < 0.40:
        lines.append("LES MINES BAISSENT")
    move = move_line(earlier, now)
    if move not in lines and not move.startswith("PRESQUE"):
        lines.append(move)
    if not lines:
        lines.append("LE MONDE SE TIENT")
    return lines


# chip : un mot pour la pastille. lines : la phrase entiere, sur une ou deux lignes.
VITALS = (
    ("pop", "POPULATION", ("NOMBRE", "DE GENS")),
    ("fpc", "NOURRITURE", ("À MANGER", "PAR PERSONNE")),
    ("iopc", "INDUSTRIE", ("OBJETS FAITS", "PAR PERSONNE")),
    ("ppolx", "POLLUTION", ("POLLUTION",)),
    ("nrfr", "RESSOURCES", ("MÉTAL", "QU'IL RESTE")),
)


def vital_phrase(item) -> str:
    return " ".join(item[2])


def vital_tone(key: str, value: float) -> str:
    """'ok', 'warn' ou 'bad'. Population et industrie restent neutres : croitre n'est pas gagner."""
    if key == "fpc":
        if value < 300:
            return "bad"
        if value < 420:
            return "warn"
        return "ok"
    if key == "ppolx":
        if value >= 10:
            return "bad"
        if value >= 6:
            return "warn"
        return "ok"
    if key == "nrfr":
        if value < 0.20:
            return "bad"
        if value < 0.40:
            return "warn"
        return "ok"
    return "ink"
