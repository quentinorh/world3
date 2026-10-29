"""Boucle du jeu. La fenetre logique fait 720x720, l'ecran du Raspberry."""

from __future__ import annotations

import math
import os
import random
import time

import pygame

from device.accel import Accel
from device.power import halt_machine, on_pi
from device.screen import logical_pos, open_screen, present_frame

from .audio import SCREEN_SEMI, Kit, law_semi, notch_semi, year_semi
from .content import (
    EVENTS,
    FIN,
    HORIZON_CAP,
    INTRO,
    ISS_CARD,
    LAWS,
    SHOCK_BY_ID,
    card_info,
    choice_parts,
    dilemma_at,
    gap_event_count,
    next_stop,
    plan_events,
    shock_banner,
)
from .planet import Planet
from .render import (
    CARD_STRIDE,
    PLOT_RECT,
    draw,
    planet_center,
    slider_hit,
    slider_notch,
    year_from_plot_x,
)
from .save import MAX_SEALS, GameState
from .sim import (
    baseline_schedule,
    close_schedules,
    judge,
    move_line,
    peek_schedule,
    poll_schedules,
    run_schedule,
    talk_lines,
    TURN_YEARS,
    warm_schedule,
)

PITCH_LIMIT = 1.22
# Rotation pendant un tour, bien au-dessus du repos (famine ~0,16).
# Negatif, comme le repos : d'ouest en est.
TURN_SPIN = -4.0
# Une année met toujours ce temps à passer. Un long vide ne s'accélère pas.
YEAR_PACE = 0.62
# Horloge des decors, en tours par seconde : orbites, nuages, motifs des
# cartes, onde d'evenement, temoins du bouton. Fixe : les crans changent le
# nombre de satellites, jamais le rythme.
DECOR_RATE = 0.65
# Image la plus longue comptee. Une simulation ou un son synthetise peut
# couter 200 ms : sans borne, les animations sautent d'un coup.
DT_MAX = 0.1
# Axe Y du BMA220 → offset de yaw (point de vue), pas une vitesse.
# Le spin avance toujours dans self.yaw ; l'offset ne s'integre pas (pas d'inertie).
# Gain en radians par g. Inverser via device.accel.AXIS_Y.
TILT_Y_GAIN = 1.4
TILT_YAW_MAX = 0.95
TILT_Y_DEADZONE = 0.06
# Lissage du Y : plus bas = moins d'a-coups (rad/s de rappel vers la cible).
TILT_Y_SMOOTH = 5.0
TILT_Y_SMOOTH2 = 7.0
from .theme import BG, EVENT_WAVE, H, MOOD_SPIN, PLANET_R, W


def ease(rate, dt):
    """Part du chemin faite en dt, pour un rappel de constante `rate`.

    min(1, rate * dt) allait plus vite quand les images tombaient : la
    meme detente doit durer autant a 30 ou a 12 images par seconde.
    """
    return 1.0 - math.exp(-rate * dt)


class App:
    def __init__(self, surf, window, font, state: GameState, shots=False, panel=None):
        self.surf = surf
        self.window = window
        self.font = font
        self.state = state
        self.shots = shots
        self.panel = panel
        self.alive = True
        self.pace = None
        self.screen = "monde"
        self.overlay = None
        self.intro_i = 0
        self.law = 0
        self.preview = None
        self.pick = None
        self._choice_key = None
        self._choice_traj = None
        self.draft = None
        self.law_pan = 0.0
        self.law_anim = None
        self.slide_dest = None
        self.pan_grab = 0.0
        self._pan_pointer = None
        self.event_prev = None
        self.event_pan = 0.0
        self.event_anim = None
        self.knob = float(state.notches[0])
        self.yaw = 0.4
        self.pitch = 0.1
        # Orientation des orbites liee au geste, pas a la rotation de repos.
        self.sat_yaw = 0.0
        self.spin = -0.0375
        self.pitch_spin = 0.0
        # Offset de regard (axe Y). yaw continue de tourner en dessous.
        self.tilt_yaw = 0.0
        self._y_smooth = 0.0
        self._y_smooth2 = 0.0
        self._tilt_key_yaw = 0.0
        self.accel = Accel.open()
        # Horloge unique des decors, en secondes de jeu mises a l'echelle.
        self.beat = 0.0
        self._wave_t0 = 0.0
        self.rockets = []
        self.planet = Planet()
        self.visible = {"pop", "fpc", "iopc", "ppolx", "nrfr"}
        self.curve = "pop"
        self.settings_back = None
        self._confirm_back = None
        self.confirm = None
        self.read_pinned = False
        self.read_year = state.year
        self.pressed = None
        self.down = None
        self.drag = None
        self.moved = False
        self.hits = None
        self.toast = ""
        self.toast_bad = True
        self.toast_t = 0.0
        self.talk_i = 0
        self.talk_t = 0.0
        self.year_flash = 0.0
        self.seal_flash = 0.0
        self.event = None
        self.shock = None
        # Horloge du graphe d'événement : elle ne part qu'une fois la courbe prête.
        self.shock_sweep = 0.0
        self._shock_ready = False
        self.reveal_kind = None
        self.reveal_t = 0.0
        self.title = None
        self._event_wave_cycle = None
        self._seal_announce = False
        self.scroll = 0
        self._pending_shock = None
        self._stop_kind = None
        self.catchup = None
        self.catch_ready = False
        self.catch_a = None
        self.catch_b = None
        self.catch_w0 = ""
        self.catch_w1 = ""
        self.catch_line = ""
        self.catch_shock = ""
        self.dirty = False
        self.save_acc = 0.0
        self._traj = None
        self._traj_key = None
        self._base = None
        self._turn_from = None
        self._turn_target = None
        self.stops = []
        self.turn_anim = None
        # 1 : chiffres visibles. 0 : titres et barres seulement.
        self.stats_open = True
        self.stats_t = 1.0
        self._stats_anim = None
        # Temps passé ouverte avant repli automatique (page planète).
        self._stats_idle = 0.0
        self._stats_hold = 5.0
        self._hold_depart = False
        self.fiche = None
        self.fiche_back = None
        self.council_phase = state.council_phase
        self.fin_kind = ""
        self.fin_word = ""
        self.fin_can = False
        self._turn_heard = False
        self.last_shown = int(state.year)
        self.audio = False
        self.kit = Kit()
        self._year_heard = None
        self._notch_heard = None
        self._block_latch = False

    def _init_audio(self):
        try:
            self.kit.load()
            self.audio = self.kit.ready
        except (pygame.error, OSError, ValueError):
            self.audio = False

    def cue(self, name, semi=0, force=False, detent=False):
        if not self.audio:
            return
        if not force and not self.state.sound:
            return
        self.kit.play(name, semi, detent)

    def hear_year(self, year):
        step = int(round(year))
        if step == self._year_heard:
            return
        self._year_heard = step
        self.cue("seek", semi=year_semi(step), detent=True)

    def hear_notch(self, notch):
        if notch == self._notch_heard:
            return
        self._notch_heard = notch
        self.cue("snap", semi=notch_semi(notch), detent=True)

    def traj(self):
        horizon = int(self.state.horizon)
        key = (tuple(self.state.schedule), tuple(self.state.shocks), horizon)
        if key != self._traj_key:
            hit = peek_schedule(self.state.schedule, self.state.shocks, horizon)
            if hit is None:
                # Le premier calcul (démarrage, nouvelle partie) n'a rien à montrer.
                # Ensuite on garde l'ancienne courbe le temps que la nouvelle arrive.
                if self._traj is None or self.shots:
                    hit = run_schedule(self.state.schedule, self.state.shocks, horizon)
                else:
                    warm_schedule(self.state.schedule, self.state.shocks, horizon)
                    return self._traj
            self._traj = hit
            self._traj_key = key
        return self._traj

    def baseline(self):
        horizon = int(self.state.horizon)
        if self._base is not None and getattr(self, "_base_h", None) == horizon:
            return self._base
        hit = peek_schedule(baseline_schedule(), (), horizon)
        if hit is None:
            if self.shots:
                hit = run_schedule(baseline_schedule(), year_max=horizon)
            else:
                warm_schedule(baseline_schedule(), (), horizon)
                return None
        self._base = hit
        self._base_h = horizon
        return hit

    def _draft_notches(self):
        if self.draft is None:
            return self.state.notches
        return self.draft

    def _live_notches(self):
        notches = list(self._draft_notches())
        if self.preview is not None:
            notches[self.law] = int(self.preview)
        return tuple(notches)

    def _notch_at(self, index):
        if self.preview is not None and index == self.law:
            return int(self.preview)
        return int(self._draft_notches()[index])

    def _law_notch(self):
        return self._notch_at(self.law)

    def _law_sliding(self):
        return self.law_anim is not None or abs(self.law_pan) > 16

    def focus_law(self):
        """Orientation mise en avant pendant le slide."""
        count = len(LAWS)
        if abs(self.law_pan) < CARD_STRIDE * 0.5:
            return self.law
        if self.slide_dest is not None:
            return self.slide_dest
        if self.law_pan > 0:
            return (self.law - 1) % count
        return (self.law + 1) % count

    def law_pages(self):
        """Pages visibles : (index, décalage horizontal)."""
        pages = [(self.law, self.law_pan)]
        count = len(LAWS)
        if self.law_pan > 1:
            other = self.slide_dest if self.slide_dest is not None else (self.law - 1) % count
            pages.append((other, self.law_pan - CARD_STRIDE))
        elif self.law_pan < -1:
            other = self.slide_dest if self.slide_dest is not None else (self.law + 1) % count
            pages.append((other, self.law_pan + CARD_STRIDE))
        return pages

    def _apply_law(self, index):
        self.preview = None
        self.law = index
        shown = self._notch_at(index)
        self.knob = float(shown)
        self._notch_heard = shown

    def _end_law_slide(self):
        dest = self.slide_dest
        if dest is not None and dest != self.law:
            if self.law_pan < 0:
                self.law_pan += CARD_STRIDE
            elif self.law_pan > 0:
                self.law_pan -= CARD_STRIDE
            self._apply_law(dest)
        if abs(self.law_pan) < 2:
            self.law_pan = 0.0
        self.slide_dest = None
        self.law_anim = None

    def _skip_law_slide(self):
        if self.slide_dest is not None and self.slide_dest != self.law:
            self._apply_law(self.slide_dest)
        self.law_pan = 0.0
        self.slide_dest = None
        self.law_anim = None

    def _start_law_slide(self, target, dest):
        origin = float(self.law_pan)
        dist = abs(float(target) - origin)
        dur = max(0.14, 0.32 * dist / CARD_STRIDE) if dist else 0.01
        self.slide_dest = dest
        self.law_anim = (origin, float(target), 0.0, dur)
        if dest is not None:
            self.cue("seek", semi=law_semi(dest), detent=True)

    def _advance_law_slide(self, dt):
        if self.law_anim is None:
            return
        if self.drag == "cards" and self.moved:
            return
        origin, target, elapsed, dur = self.law_anim
        elapsed += dt
        u = 1.0 if dur <= 0 else min(1.0, elapsed / dur)
        eased = 1 - (1 - u) ** 3
        self.law_pan = origin + (target - origin) * eased
        self.law_anim = (origin, target, elapsed, dur)
        if u >= 1:
            self._end_law_slide()

    def _release_law_pan(self):
        """Lâche le slide : on termine le changement, ou la carte revient."""
        count = len(LAWS)
        horizontal = True
        if self.down is not None and self._pan_pointer is not None:
            px, py = self._pan_pointer
            ox, oy = self.drag_origin
            horizontal = abs(px - ox) > abs(py - oy) * 1.4
        if horizontal and self.law_pan > 96:
            self._start_law_slide(float(CARD_STRIDE), (self.law - 1) % count)
        elif horizontal and self.law_pan < -96:
            self._start_law_slide(float(-CARD_STRIDE), (self.law + 1) % count)
        elif abs(self.law_pan) < 1:
            self.law_pan = 0.0
            self.slide_dest = None
            self.law_anim = None
        else:
            self.slide_dest = None
            self._start_law_slide(0.0, None)

    def pending_seals(self):
        """Jetons encore libres : l'ecart au cran pose, pas le chemin parcouru."""
        spent = sum(abs(int(a) - int(b)) for a, b in zip(self.state.notches, self._live_notches()))
        return max(0, int(self.state.seals) - spent)

    def preview_traj(self):
        live = self._live_notches()
        if live == tuple(self.state.notches):
            return None
        horizon = int(self.state.horizon)
        key = (live, tuple(self.state.schedule), tuple(self.state.shocks), horizon)
        if key == getattr(self, "_preview_key", None):
            return self._preview_traj
        sched = tuple(self.state.schedule) + ((round(self.state.year, 3), live),)
        try:
            traj = peek_schedule(sched, self.state.shocks, horizon)
        except RuntimeError:
            traj = None
        if traj is None:
            warm_schedule(sched, self.state.shocks, horizon, front=True)
            return None
        self._preview_key = key
        self._preview_traj = traj
        return traj

    def _choice_world(self, pick):
        """Calendrier si ce choix était pris. None s'il ne change rien."""
        if pick not in ("a", "b") or not self.event:
            return None
        _label, index, delta, _sub, shock = choice_parts(self.event[pick])
        when = round(float(self.event.get("year") or self.state.year), 3)
        sched = tuple(self.state.schedule)
        shocks = tuple(self.state.shocks)
        if index is not None and delta and when < self.state.horizon:
            notches = list(self.state.notches)
            nxt = max(0, min(4, int(notches[index]) + int(delta)))
            if nxt != int(notches[index]):
                notches[index] = nxt
                sched = sched + ((when, tuple(notches)),)
        if shock and shock not in self.state.shock_ids() and when < self.state.horizon:
            shocks = tuple(sorted(shocks + ((when, str(shock)),)))
        if sched == tuple(self.state.schedule) and shocks == tuple(self.state.shocks):
            return None
        return sched, shocks

    def _warm_choices(self):
        """Les deux réponses pendant que la carte se lit."""
        if not self.event:
            return
        mark = (
            self.event.get("id"),
            tuple(self.state.schedule),
            tuple(self.state.shocks),
            int(self.state.horizon),
        )
        if mark == getattr(self, "_warm_choice_mark", None):
            return
        self._warm_choice_mark = mark
        horizon = int(self.state.horizon)
        for pick in ("a", "b"):
            world = self._choice_world(pick)
            if world is not None:
                warm_schedule(world[0], world[1], horizon, front=True)

    def _warm_council_edges(self):
        """Cran voisins du curseur, dès la carte d'ouverture.

        Le premier geste n'attend pas le modèle : ces mondes tournent
        pendant la lecture.
        """
        if self.state.year >= self.state.horizon - 0.01:
            return
        focus = self.focus_law()
        live = self._live_notches()
        mark = (
            focus, live, tuple(self.state.schedule), tuple(self.state.shocks),
            int(self.state.horizon),
        )
        if mark == getattr(self, "_warm_edge_mark", None):
            return
        self._warm_edge_mark = mark
        horizon = int(self.state.horizon)
        base = list(live)
        current = int(base[focus])
        seen = set()
        for step in (1, -1, 2, -2, 3, -3, 4, -4):
            fitted, _blocked = self._fit_notch(focus, current + step)
            if fitted in seen or fitted == current:
                continue
            seen.add(fitted)
            notches = list(base)
            notches[focus] = fitted
            if tuple(notches) == tuple(self.state.notches):
                continue
            sched = tuple(self.state.schedule) + (
                (round(self.state.year, 3), tuple(notches)),
            )
            warm_schedule(sched, self.state.shocks, horizon)

    def dilemma_traj(self):
        """Le monde si le choix surligné était pris.

        Le monde déjà en cours s'il ne change rien. None tant que le calcul
        de ce choix n'est pas prêt : ce n'est pas un autre choix.
        """
        if self.pick not in ("a", "b") or not self.event:
            return None
        world = self._choice_world(self.pick)
        if world is None:
            return self.traj()
        sched, shocks = world
        horizon = int(self.state.horizon)
        key = (self.pick, self.event.get("id"), sched, shocks, horizon)
        if key == getattr(self, "_choice_key", None):
            return self._choice_traj
        try:
            traj = peek_schedule(sched, shocks, horizon)
        except RuntimeError:
            traj = None
        if traj is None:
            warm_schedule(sched, shocks, horizon, front=True)
            return None
        self._choice_key = key
        self._choice_traj = traj
        return traj

    def shock_traj(self):
        """Le monde si l'événement affiché tombait. None s'il ne change rien."""
        sh = self.shock
        if not sh:
            return None
        sid = str(sh.get("id") or "")
        if not sid:
            return None
        when = round(float(sh.get("year") or self.state.year), 3)
        if sid in self.state.shock_ids() or when >= self.state.horizon:
            return None
        shocks = tuple(self.state.shocks)
        shocks = tuple(sorted(shocks + ((when, sid),)))
        horizon = int(self.state.horizon)
        key = (sid, when, tuple(self.state.shocks), tuple(self.state.schedule), horizon)
        if key == getattr(self, "_shock_key", None):
            return self._shock_traj
        try:
            traj = peek_schedule(self.state.schedule, shocks, horizon)
        except RuntimeError:
            traj = None
        if traj is None:
            warm_schedule(self.state.schedule, shocks, horizon, front=True)
            return None
        self._shock_key = key
        self._shock_traj = traj
        return traj

    def word_at(self, year):
        traj = self.traj()
        return judge(traj.sample(year), traj.sample(year - 5), year)

    def word_now(self):
        return self.word_at(self.state.year)

    def shown_year(self):
        """Année dessinée. Pendant un tour, elle avance au lieu de sauter."""
        if self.turn_anim is None:
            return self.state.year
        origin, dest, elapsed, dur = self.turn_anim
        if dur <= 0:
            return dest
        u = min(1.0, elapsed / dur)
        return origin + (dest - origin) * u

    def read_at(self):
        if not self.read_pinned:
            return self.state.year
        return self.read_year

    def logical_pos(self, pos):
        return logical_pos(self.window, self.surf, pos)

    def present(self):
        present_frame(self.window, self.surf, self.panel)

    def boot(self):
        self.surf.fill(BG)
        self.font.blit(self.surf, "WORLD3", W // 2, 300, 6, (236, 230, 216), align="center")
        self.font.blit(self.surf, "DE 1900 À 2100", W // 2, 380, 2, (176, 168, 154), align="center")
        t0 = time.perf_counter()
        self.present()
        self._pace_boot("titre", t0)
        t0 = time.perf_counter()
        self._init_audio()
        self._pace_boot("audio", t0)
        # Le scénario gris part en même temps que le monde déjà joué.
        warm_schedule(baseline_schedule(), (), self.state.horizon)
        t0 = time.perf_counter()
        self.traj()
        self._pace_boot("calcul", t0)

    def _pace_boot(self, step, t0):
        if self.pace is not None:
            self.pace.boot(step, (time.perf_counter() - t0) * 1000.0)

    def _pace_page(self):
        if self.overlay == "title" and self.title:
            return "titre:" + str(self.title)
        if self.overlay:
            return str(self.overlay)
        return str(self.screen or "monde")

    def _pace_act(self):
        if self.turn_anim is not None:
            return "annee"
        if self.law_anim is not None:
            return "loi"
        if self.event_anim is not None:
            return "carte"
        if self.drag:
            return "doigt:" + str(self.drag)
        return "repos"

    def goto(self, screen):
        if screen == self.screen:
            return
        self.screen = screen
        self.preview = None
        self.cue("select", semi=SCREEN_SEMI[screen])
        if screen == "courbes":
            self._year_heard = int(round(self.read_at()))

    def shift_law(self, delta):
        if not delta:
            return
        if self.law_anim is not None:
            self._skip_law_slide()
        self.preview = None
        dest = (self.law + delta) % len(LAWS)
        self._start_law_slide(float(-delta * CARD_STRIDE), dest)

    def set_law(self, index):
        count = len(LAWS)
        if index == self.law and self.law_anim is None and abs(self.law_pan) < 1:
            return
        if self.law_anim is not None:
            self._skip_law_slide()
        raw = (index - self.law) % count
        if raw == 0:
            return
        sign = 1 if raw <= count - raw else -1
        self.preview = None
        self._start_law_slide(float(-sign * CARD_STRIDE), index)

    def _fit_notch(self, law, wanted):
        """Ramene le cran dans le budget. Revenir vers le cran pose ne coute rien."""
        wanted = max(0, min(4, int(wanted)))
        origin = int(self.state.notches[law])
        others = 0
        for i, (a, b) in enumerate(zip(self.state.notches, self._draft_notches())):
            if i != law:
                others += abs(int(a) - int(b))
        room = max(0, int(self.state.seals) - others)
        low = max(0, origin - room)
        high = min(4, origin + room)
        fitted = min(high, max(low, wanted))
        return fitted, fitted != wanted

    def _stage_notch(self, law, value):
        notches = list(self._draft_notches())
        notches[law] = int(value)
        self.draft = tuple(notches)

    def commit_notches(self, new_notches, announce=True):
        old = self.state.notches
        if new_notches == old:
            return True
        if self.state.year >= self.state.horizon - 0.01:
            self.toast = "PLUS D'ANNÉES"
            self.toast_bad = True
            self.toast_t = 1.2
            self.cue("blocked")
            return False
        cost = sum(abs(a - b) for a, b in zip(old, new_notches))
        if cost > self.state.seals:
            self.toast = "PLUS DE JETON"
            self.toast_bad = True
            self.toast_t = 1.2
            self.cue("blocked")
            return False
        self.state.seals -= cost
        self.state.schedule.append((round(self.state.year, 3), tuple(new_notches)))
        changed = [(i, b - a) for i, (a, b) in enumerate(zip(old, new_notches)) if a != b]
        if announce and len(changed) == 1:
            index, delta = changed[0]
            self.toast = LAWS[index]["up" if delta > 0 else "down"]
            self.toast_bad = False
            self.toast_t = 1.5
        self.spin -= 0.45
        self.dirty = True
        self._preview_key = None
        if announce:
            paid = next((b for a, b in zip(old, new_notches) if a != b), None)
            if paid is not None:
                self.hear_notch(paid)
        return True

    def bump(self, delta):
        if self.draft is None:
            self.draft = tuple(self.state.notches)
        current = int(self.draft[self.law])
        nxt, blocked = self._fit_notch(self.law, current + delta)
        if nxt == current:
            if blocked:
                self.toast = "PLUS DE JETON"
                self.toast_bad = True
                self.toast_t = 1.2
            self.cue("blocked")
            return
        self._stage_notch(self.law, nxt)
        self.preview = None
        self.hear_notch(nxt)

    def validate_orientations(self):
        live = self._live_notches()
        if live != tuple(self.state.notches):
            if not self.commit_notches(live, announce=False):
                return
        self.draft = None
        self.preview = None
        self.open_dilemma()

    def toggle_series(self, key):
        if key in self.visible:
            self.visible.remove(key)
            self.cue("uncheck")
        else:
            self.visible.add(key)
            self.cue("check")

    def select_curve(self, key):
        if key == self.curve:
            return
        self.curve = key
        self.cue("select", semi=2)

    def follow_now(self):
        self.read_pinned = False
        self._year_heard = int(round(self.state.year))
        self.cue("back")

    def toggle_sound(self):
        self.state.sound = not self.state.sound
        self.dirty = True
        self.cue("toggle-on" if self.state.sound else "toggle-off", force=True)

    def ask_reset(self):
        self._confirm_back = self.overlay
        self.confirm = "reset"
        self.overlay = "confirm"
        self.cue("warning")

    def go_home(self):
        self.cue("back")
        self.alive = False

    def ask_poweroff(self):
        self._confirm_back = self.overlay
        self.confirm = "off"
        self.overlay = "confirm"
        self.cue("warning")

    def cancel_reset(self):
        self.overlay = self._confirm_back
        self._confirm_back = None
        self.confirm = None
        self.cue("cancel")

    def do_reset(self):
        self.state.reset_world()
        self._traj = None
        self._traj_key = None
        self.preview = None
        self.draft = None
        self.law_pan = 0.0
        self.law_anim = None
        self.slide_dest = None
        self.law = 0
        self.knob = 0.0
        self.read_pinned = False
        self.catchup = None
        self.catch_ready = False
        self.turn_anim = None
        self._turn_heard = False
        self._turn_from = None
        self._turn_target = None
        self._pending_shock = None
        self._stop_kind = None
        self.stops = []
        self.rockets = []
        self.shock = None
        self.catch_shock = ""
        self.fiche = None
        self.fiche_back = None
        self.settings_back = None
        self._confirm_back = None
        self.confirm = None
        self.council_phase = ""
        self.title = None
        self._seal_announce = False
        self.intro_i = 0
        self.overlay = "intro"
        self.screen = "monde"
        self.last_shown = int(self.state.year)
        self.dirty = False
        self.cue("delete")

    def do_poweroff(self):
        if not self.shots:
            self.state.save()
            self.dirty = False
        if halt_machine():
            self.alive = False
            return
        if on_pi():
            self.overlay = self._confirm_back
            self._confirm_back = None
            self.confirm = None
            self.toast = "IMPOSSIBLE"
            self.toast_bad = True
            self.toast_t = 1.6
            self.cue("blocked")
            return
        self.alive = False

    def intro_next(self):
        if self.intro_i < len(INTRO) - 1:
            self.intro_i += 1
            self.cue("forward")
            return
        self.state.seen_intro = True
        self.overlay = None
        self.dirty = True
        self.cue("check")
        self.maybe_open()

    def prepare_catchup(self):
        start, end = self.catchup
        traj = self.traj()
        self.catch_a = traj.sample(start)
        self.catch_b = traj.sample(end)
        self.catch_w0 = judge(self.catch_a, traj.sample(start - 5), start)
        self.catch_w1 = judge(self.catch_b, traj.sample(end - 5), end)
        self.catch_line = move_line(self.catch_a, self.catch_b)
        self.catch_shock = ""
        for when, sid in self.state.shocks:
            if start + 1e-6 < when <= end + 1e-6 and sid in SHOCK_BY_ID:
                self.catch_shock = SHOCK_BY_ID[sid]["title"]
                break
        self.catch_ready = True

    def dismiss_catchup(self):
        self.catchup = None
        self.catch_ready = False
        self.overlay = None
        self.cue("close")
        self.maybe_open()

    def action_label(self):
        if self.state.year >= self.state.horizon - 0.01:
            return "NOUVELLE PARTIE"
        kind, year = next_stop(self.state.year, self.state.horizon)
        if kind == "fin":
            return f"{int(year)} - L'HORIZON"
        return f"{int(year)} - PROCHAIN CONSEIL"

    def headlines(self, year=None):
        traj = self.traj()
        if year is None:
            year = self.state.year
        lines = list(talk_lines(traj.sample(year), traj.sample(year - 5)))
        banner = shock_banner(self.state.shocks, year)
        if banner and banner not in lines:
            lines.insert(0, banner)
        return lines or ["LE MONDE ATTEND"]

    def open_reader(self, name):
        self.overlay = name
        self.scroll = 0
        self.cue("forward")

    def close_reader(self):
        self.overlay = "reglages" if self.overlay in ("aide", "info") else None
        self.scroll = 0
        self.cue("back")

    def open_fiche(self, title, paragraphs, back):
        lines = tuple(paragraphs) if paragraphs else ("Pas de fiche pour cette carte.",)
        self.fiche = (title, lines)
        self.fiche_back = back
        self.overlay = "fiche"
        self.scroll = 0
        self.cue("forward")

    def close_fiche(self):
        self.overlay = self.fiche_back or None
        self.fiche_back = None
        self.scroll = 0
        self.cue("back")

    def open_pause(self):
        if self.overlay not in (None,):
            return
        self.overlay = "pause"
        self.cue("select", semi=0)

    def close_pause(self):
        if self.overlay == "pause":
            self.overlay = None
            self.cue("forward")

    def open_graphs(self):
        if self.turn_anim is not None or self.overlay not in (None,):
            return
        self.overlay = "courbes"
        self.read_pinned = False
        self._year_heard = int(round(self.state.year))
        self.cue("select", semi=2)

    def open_settings(self):
        if self.turn_anim is not None or self.overlay in (
            "intro", "title", "reglages", "aide", "info", "fiche", "confirm",
        ):
            return
        self.settings_back = self.overlay
        self.overlay = "reglages"
        self.cue("select", semi=3)

    def close_panel(self):
        if self.overlay in ("aide", "info"):
            self.overlay = "reglages"
            self.cue("back")
            return
        if self.overlay == "reglages":
            self.overlay = self.settings_back
            self.settings_back = None
            self.cue("back")
            return
        if self.overlay == "courbes":
            self.overlay = None
            self.scroll = 0
            self.cue("back")

    def toggle_stats(self):
        """Ouvre ou ferme la barre des chiffres. Le depart en cours n'est pas interrompu."""
        if self.overlay is not None or self._hold_depart:
            return
        self._aim_stats(not self.stats_open)
        self.cue("select" if self.stats_open else "back", semi=1)

    def _aim_stats(self, open_, hold=None):
        dest = 1.0 if open_ else 0.0
        self.stats_open = bool(open_)
        if open_:
            self._stats_idle = 0.0
            self._stats_hold = 5.0 if hold is None else float(hold)
        if self._stats_anim is not None and abs(self._stats_anim[1] - dest) < 0.001:
            return
        if abs(self.stats_t - dest) < 0.001:
            self.stats_t = dest
            self._stats_anim = None
            return
        self._stats_anim = (float(self.stats_t), dest, 0.0, 0.32)

    def _step_stats(self, dt):
        if self._stats_anim is not None:
            origin, dest, elapsed, dur = self._stats_anim
            elapsed += dt
            u = 1.0 if dur <= 0 else min(1.0, elapsed / dur)
            eased = 1 - (1 - u) ** 3
            self.stats_t = origin + (dest - origin) * eased
            if u >= 1:
                self.stats_t = dest
                self._stats_anim = None
            else:
                self._stats_anim = (origin, dest, elapsed, dur)
        if (
            self.stats_open
            and self.overlay is None
            and not self._hold_depart
            and self._stats_anim is None
            and self.stats_t >= 0.999
        ):
            self._stats_idle += dt
            if self._stats_idle >= self._stats_hold:
                self._aim_stats(False)
        if self._hold_depart and self.overlay is not None:
            self._hold_depart = False
            return
        if self._hold_depart and self._stats_anim is None and self.stats_t <= 0.001:
            self.stats_t = 0.0
            self._hold_depart = False
            if self.turn_anim is None:
                self._launch_years()

    def depart(self):
        """Lance les annees vers le prochain conseil, ou vers l'horizon.

        La barre ouverte se ferme d'abord. La Terre ne part qu'une fois fermée.
        """
        if self.overlay or self.turn_anim is not None or self._hold_depart:
            return
        if self.stats_open or self.stats_t > 0.001 or self._stats_anim is not None:
            self._aim_stats(False)
            self._hold_depart = True
            return
        self._launch_years()

    def _launch_years(self):
        if self.state.year >= self.state.horizon - 0.01:
            self.ask_reset()
            return
        kind, target = next_stop(self.state.year, self.state.horizon)
        before = gap_event_count(self.state.shocks, target)
        events = plan_events(
            self.state.rng_seed,
            self.state.year,
            target,
            self.state.shock_ids(),
            before,
        )
        self.stops = [("event", year, sid) for year, sid in events]
        self.stops.append((kind, float(target), None))
        self.screen = "monde"
        self._next_leg()

    def play_turn(self):
        self.depart()

    def _next_leg(self):
        if not self.stops:
            return
        _kind, year, _sid = self.stops[0]
        start = float(self.state.year)
        if year <= start + 1e-6:
            self._open_stop()
            return
        span = max(0.0, year - start)
        dur = span * YEAR_PACE
        self.turn_anim = (start, float(year), 0.0, dur)
        # Même vitesse dès la première image. Sinon, après une carte lue
        # longtemps, la Terre repart du repos et n'atteint le tour qu'au bout.
        self.spin = TURN_SPIN
        # L'année courante est déjà posée : pas de seek en même temps que le départ.
        self._year_heard = int(round(start))
        self._turn_heard = True
        self.cue("progress-step")

    def _advance_turn(self, dt):
        origin, dest, elapsed, dur = self.turn_anim
        elapsed += dt
        self.hear_year(origin + (dest - origin) * min(1.0, elapsed / dur if dur else 1))
        self.turn_anim = (origin, dest, elapsed, dur)
        if elapsed < dur + 0.12:
            return
        self.turn_anim = None
        self._open_stop()

    def _open_stop(self):
        if not self.stops:
            return
        kind, year, sid = self.stops.pop(0)
        self.turn_anim = None
        self.state.year = float(year)
        self.last_shown = int(round(year))
        self.year_flash = 0.45
        self.dirty = True
        if kind == "event" and sid:
            self._show_event_card(year, sid)
            return
        if kind == "conseil":
            self.arrive_council(year)
            return
        self.open_fin()

    def _show_event_card(self, year, sid):
        spec = SHOCK_BY_ID.get(sid)
        if spec is None:
            self.state.pending = None
            if self.stops:
                self._next_leg()
            return
        self.shock = {
            "id": sid,
            "year": int(round(float(year))),
            "title": spec["title"],
            "lines": spec["lines"],
            "effect": spec.get("effect") or "",
            "info": card_info(spec),
        }
        self.state.pending = (float(year), sid)
        self.dirty = True
        self._arm_title("event")
        # Le graphe de la carte se calcule pendant que le titre est à l'écran.
        self.shock_traj()

    def show_pending(self):
        if not self.state.pending:
            return
        year, sid = self.state.pending
        self._show_event_card(year, sid)

    def dismiss_shock(self):
        """L'evenement est joue. La Terre repart jusqu'au prochain arret."""
        pending = self.state.pending
        self.state.pending = None
        self.shock = None
        self.overlay = None
        if pending:
            year, sid = pending
            if sid not in self.state.shock_ids():
                self.state.shocks.append((float(year), sid))
                self.state.shocks.sort()
            # Déjà calculé pendant la lecture de la carte. On garde l'ancienne
            # planète si le résultat n'est pas encore rangé.
            self._traj_key = None
            self.dirty = True
        self.screen = "monde"
        # Un seul départ : _next_leg / depart joue progress-step.
        if self.stops:
            self._next_leg()
            return
        self.turn_anim = None
        if self.state.year < self.state.horizon - 0.01:
            self.depart()

    def arrive_council(self, year):
        self.state.year = float(year)
        granted = int(round(float(year)))
        self._seal_announce = False
        if self.state.council_granted != granted:
            self.state.seals = MAX_SEALS
            self.state.council_granted = granted
            self._seal_announce = True
        self.council_phase = "orient"
        self.state.council_phase = "orient"
        self.draft = tuple(self.state.notches)
        self.preview = None
        self.law_pan = 0.0
        self.law_anim = None
        self.slide_dest = None
        self.knob = float(self.draft[self.law])
        self.dirty = True
        self._arm_title("orient")

    def _arm_title(self, kind):
        """Carte d'ouverture. Elle attend le bouton Continuer."""
        self.title = kind
        self.overlay = "title"
        # Même rythme que _motif_event : une pulsation par tour de phase.
        if kind == "event":
            # Phase à 0 : le premier bip et la première onde partent ensemble.
            # On repere l'instant, sans toucher a l'horloge des autres décors.
            self._wave_t0 = self.beat
            self._event_wave_cycle = 0
        sound = {"orient": "council", "event": "warning", "dilemma": "council"}
        self.cue(sound.get(kind, "open"))

    def dismiss_title(self):
        kind = self.title
        if not kind:
            return
        self.title = None
        if kind in ("orient", "council"):
            if self._seal_announce:
                self.seal_flash = 0.7
                self._seal_announce = False
            self.overlay = "conseil"
        elif kind == "event":
            self.shock_sweep = 0.0
            self._shock_ready = False
            self.overlay = "shock"
        elif kind == "dilemma":
            self.overlay = "event"
        else:
            self.overlay = None
            return
        self.cue("forward")

    def open_dilemma(self, intro=True):
        sample = self.traj().sample(self.state.year)
        year = int(round(self.state.year))
        if (
            ISS_CARD.get("id")
            and ISS_CARD["id"] not in self.state.events_done
            and year >= int(ISS_CARD.get("year") or 2030)
        ):
            self.event = dict(ISS_CARD)
            self.event["year"] = year
        else:
            self.event = dilemma_at(
                self.state.year, sample, self.state.notches, self.state.events_done
            )
        self.council_phase = "dilemma"
        self.state.council_phase = "dilemma"
        self.pick = None
        self._choice_key = None
        self.dirty = True
        self._warm_choices()
        if intro:
            self._end_event_slide()
            self._arm_title("dilemma")
            return
        # Enchaînement : pas de seconde carte DILEMME.
        self.title = None
        self.overlay = "event"

    def motif_phase(self):
        """Phase des motifs des cartes. L'onde d'evenement part de zero."""
        if self.title == "event":
            return self.beat - self._wave_t0
        return self.beat

    def _event_sliding(self):
        return self.event_anim is not None

    def _start_event_slide(self, prev):
        self.event_prev = prev
        self.event_pan = float(W)
        self.event_anim = (float(W), 0.0, 0.0, 0.36)

    def _advance_event_slide(self, dt):
        if self.event_anim is None:
            return
        origin, target, elapsed, dur = self.event_anim
        elapsed += dt
        u = 1.0 if dur <= 0 else min(1.0, elapsed / dur)
        eased = 1 - (1 - u) ** 3
        self.event_pan = origin + (target - origin) * eased
        self.event_anim = (origin, target, elapsed, dur)
        if u >= 1:
            self._end_event_slide()

    def _end_event_slide(self):
        self.event_pan = 0.0
        self.event_prev = None
        self.event_anim = None

    def pick_choice(self, key):
        if self._event_sliding():
            return
        if not self.event or key not in ("a", "b") or self.pick == key:
            return
        self.pick = key
        self.cue("select")

    def validate_dilemma(self):
        if self._event_sliding():
            return
        if not self.event:
            return
        if self.pick not in ("a", "b"):
            self.toast = "CHOISIR"
            self.toast_bad = True
            self.toast_t = 0.8
            self.cue("blocked")
            return
        self.choose(self.pick)

    def choose(self, key):
        if not self.event:
            return
        prev = self.event
        _label, index, delta, _sub, shock = choice_parts(self.event[key])
        when = float(self.event.get("year") or self.state.year)
        if index is not None and delta and when < self.state.horizon:
            notches = list(self.state.notches)
            notches[index] = max(0, min(4, notches[index] + delta))
            new = tuple(notches)
            if new != self.state.notches:
                self.state.schedule.append((round(when, 3), new))
                self.knob = float(new[self.law])
        if shock and shock not in self.state.shock_ids() and when < self.state.horizon:
            self.state.shocks.append((round(when, 3), shock))
            self.state.shocks.sort()
        self.state.events_done.add(self.event["id"])
        self.event = None
        self.pick = None
        self._choice_key = None
        self._traj_key = None
        self.dirty = True
        if self._more_dilemmas():
            self.cue("check")
            self.open_dilemma(intro=False)
            self._start_event_slide(prev)
            return
        self._end_event_slide()
        self.council_phase = ""
        self.state.council_phase = ""
        self.overlay = None
        self.stops = []
        self.turn_anim = None
        self.screen = "monde"
        self.dirty = True
        # Après les dilemmes : chiffres ouverts une seconde, puis repli.
        self._aim_stats(True, hold=1.0)
        self.cue("check")

    def _more_dilemmas(self):
        """Une carte du conseil reste à poser : la station, ou un dilemme de l'année."""
        year = int(round(self.state.year))
        if (
            ISS_CARD.get("id")
            and ISS_CARD["id"] not in self.state.events_done
            and year >= int(ISS_CARD.get("year") or 2030)
        ):
            return True
        for ev in EVENTS:
            if ev.get("aside"):
                continue
            if int(ev["year"]) == year and ev["id"] not in self.state.events_done:
                return True
        return False

    def open_fin(self):
        word = self.word_at(min(self.state.year, self.state.horizon))
        holding = word in ("STABLE", "RALENTISSEMENT")
        capped = self.state.horizon >= HORIZON_CAP - 0.01
        if holding and capped:
            kind = "bout"
        elif holding:
            kind = "tient"
        else:
            kind = "chute"
        self.fin_kind = kind
        self.fin_word = word
        self.fin_can = holding and not capped
        self._fin_copy = FIN.get(kind, FIN["chute"])
        self.overlay = "fin"
        self.cue("warning" if kind == "chute" else "check")

    def close_fin(self):
        self.overlay = None
        self.cue("close")

    def continue_horizon(self):
        if not self.fin_can:
            return
        self.state.horizon = min(float(HORIZON_CAP), float(self.state.horizon) + 50)
        self._base = None
        self._traj_key = None
        warm_schedule(self.state.schedule, self.state.shocks, self.state.horizon)
        warm_schedule(baseline_schedule(), (), self.state.horizon)
        self.overlay = None
        self.dirty = True
        self.cue("forward")

    def _due_council(self):
        """Un conseil est ouvert si l'annee en est une et que son dilemme n'est pas tranche."""
        year = int(round(self.state.year))
        if year < 2030 or year % TURN_YEARS != 0 or year >= self.state.horizon - 0.01:
            return False
        for ev in EVENTS:
            if int(ev["year"]) == year and ev["id"] not in self.state.events_done:
                return True
        return False

    def maybe_open(self):
        if self.overlay or self.turn_anim is not None:
            return
        if not self.state.seen_intro:
            self.overlay = "intro"
            self.intro_i = 0
            return
        if self.state.pending:
            self.show_pending()
            return
        if self.state.council_phase == "dilemma":
            self.open_dilemma()
            return
        if self.state.council_phase == "orient" or self._due_council():
            self.arrive_council(self.state.year)

    def _on_planet(self, pos):
        cx, cy = planet_center(self)
        dx = pos[0] - cx
        dy = pos[1] - cy
        return dx * dx + dy * dy <= (PLANET_R + 16) ** 2

    def view_yaw(self):
        return self.yaw + self.tilt_yaw

    def view_sat_yaw(self):
        return self.sat_yaw + self.tilt_yaw

    def view_pitch(self):
        # Pas de pencher vertical : seule la rotation (yaw) change de point de vue.
        return max(-PITCH_LIMIT, min(PITCH_LIMIT, self.pitch))

    def _steer_planet(self, key):
        # Gauche/droite : spin. Haut/bas : ersatz de l'axe Y sans BMA220.
        if key == pygame.K_LEFT:
            self.spin -= 0.4
        elif key == pygame.K_RIGHT:
            self.spin += 0.4
        elif key == pygame.K_UP:
            self._tilt_key_yaw = max(-TILT_YAW_MAX, self._tilt_key_yaw - 0.12)
        elif key == pygame.K_DOWN:
            self._tilt_key_yaw = min(TILT_YAW_MAX, self._tilt_key_yaw + 0.12)
        else:
            return False
        return True

    def _zone(self, pos):
        if self.overlay == "courbes" and PLOT_RECT.collidepoint(pos):
            return "plot"
        if self.overlay == "conseil" and self.council_phase == "orient" and not self._law_sliding():
            if slider_hit(0).collidepoint(pos) and self.state.year < self.state.horizon:
                return "dial"
        if self.overlay in ("reglages", "title"):
            return "planet" if self._on_planet(pos) else None
        if self.overlay:
            return None
        if self._on_planet(pos):
            return "planet"
        return None

    def on_down(self, pos):
        self.down = pos
        self.drag_y = pos[1]
        self.moved = False
        self.press_hit = None
        self.drag = None
        if self.hits:
            hit = self.hits.at(pos)
            if hit:
                self.press_hit = hit
                self.pressed = hit[2]
                return
        self.drag = self._zone(pos)
        if self.overlay == "pause" and self.drag is None:
            self.drag = "planet"
        if self.drag == "planet":
            self.drag_x = pos[0]
            self.drag_y = pos[1]
            self.drag_t = time.perf_counter()
            # Le flick horizontal reprend le spin. L'inclinaison, elle, ne l'arrete pas.
            self.spin = 0.0
            return
        if self.drag == "dial":
            if self.draft is None:
                self.draft = tuple(self.state.notches)
            self.drag_origin = pos
            self.drag_notch0 = int(self.draft[self.law])
            self.preview = self.drag_notch0
            self._notch_heard = self.drag_notch0
            self._block_latch = False
            self.pan_grab = self.law_pan
            self.drag = "dial-pending"
            return
        if self.drag == "plot":
            self.read_pinned = True
            self.read_year = year_from_plot_x(pos[0], self.state.horizon)
            self.hear_year(self.read_year)
            return
        if self.overlay == "conseil" and self.council_phase == "orient":
            self.drag = "cards"
            self.pan_grab = self.law_pan
            self.drag_origin = pos
            self._pan_pointer = pos
            return

    def on_move(self, pos):
        if self.down is None:
            return
        if self.overlay in ("aide", "info", "fiche"):
            if self.press_hit is not None and self.press_hit[0].inflate(36, 36).collidepoint(pos):
                return
            if abs(pos[0] - self.down[0]) + abs(pos[1] - self.down[1]) > 8:
                self.moved = True
                self.pressed = None
                self.press_hit = None
                self.scroll -= pos[1] - self.drag_y
                self.drag_y = pos[1]
            return
        # Le tactile tremble. Un bouton reste armé tant que le doigt
        # ne quitte pas franchement sa zone.
        if self.press_hit is not None:
            rect = self.press_hit[0]
            if rect.inflate(36, 36).collidepoint(pos):
                return
            self.moved = True
            self.pressed = None
            self.press_hit = None
            return
        if abs(pos[0] - self.down[0]) + abs(pos[1] - self.down[1]) > 10:
            self.moved = True
            self.pressed = None
        if self.drag == "planet":
            now = time.perf_counter()
            dx = pos[0] - self.drag_x
            dt = max(0.008, now - self.drag_t)
            # Scroll horizontal seulement : le vertical est reserve a l'inclinaison.
            if abs(dx) >= 1:
                self.yaw -= dx * 0.01
                self.sat_yaw -= dx * 0.01
                self.spin = max(-2.2, min(2.2, -(dx / dt) * 0.01))
            self.drag_x = pos[0]
            self.drag_y = pos[1]
            self.drag_t = now
        elif self.drag in ("dial-pending", "dial", "cards"):
            if self.drag == "dial-pending":
                dx = pos[0] - self.drag_origin[0]
                dy = pos[1] - self.drag_origin[1]
                if abs(dx) < 12 and abs(dy) < 12:
                    return
                if abs(dx) > abs(dy) * 1.4:
                    self.drag = "cards"
                else:
                    self.drag = "dial"
            if self.drag == "dial":
                self._drag_dial(pos)
            else:
                self._pan_pointer = pos
                if abs(pos[0] - self.drag_origin[0]) + abs(pos[1] - self.drag_origin[1]) > 10:
                    if self.law_anim is not None:
                        self.law_anim = None
                        self.slide_dest = None
                        self.pan_grab = self.law_pan
                        self.drag_origin = pos
                if self.law_anim is None:
                    dx = pos[0] - self.drag_origin[0]
                    self.law_pan = max(-float(CARD_STRIDE), min(float(CARD_STRIDE), self.pan_grab + dx))
        elif self.drag == "plot":
            if not self.read_pinned and abs(pos[0] - self.down[0]) > 8:
                self.read_pinned = True
            if self.read_pinned:
                self.read_year = year_from_plot_x(pos[0], self.state.horizon)
                self.hear_year(self.read_year)

    def _drag_dial(self, pos):
        raw, blocked = self._fit_notch(self.law, slider_notch(pos[1]))
        if raw != self.preview:
            self.hear_notch(raw)
            self._block_latch = False
        elif blocked and not self._block_latch:
            self.cue("blocked")
            self._block_latch = True
            self.toast = "PLUS DE JETON"
            self.toast_bad = True
            self.toast_t = 0.7
        if not blocked:
            self._block_latch = False
        self.preview = raw

    def on_up(self, pos):
        if self.drag in ("dial", "dial-pending"):
            if self.drag == "dial-pending":
                self._drag_dial(pos)
            if self.preview is not None:
                self._stage_notch(self.law, self.preview)
            self.preview = None
        elif self.drag == "cards":
            self._pan_pointer = pos
            if self.law_anim is None:
                self._release_law_pan()
        elif (
            self.drag is None
            and self.overlay == "conseil"
            and self.council_phase == "orient"
            and self.moved
            and self.down is not None
        ):
            dx = pos[0] - self.down[0]
            dy = pos[1] - self.down[1]
            if abs(dx) > 80 and abs(dx) > abs(dy) * 1.4:
                self.shift_law(-1 if dx < 0 else 1)
        elif self.press_hit and not self.moved:
            rect, fn, _ident = self.press_hit
            if fn and rect.inflate(24, 24).collidepoint(pos):
                fn()
        self.down = None
        self.drag = None
        self.press_hit = None
        self.pressed = None
        self._block_latch = False

    def on_wheel(self, pos, direction):
        if self.overlay in ("aide", "info", "fiche"):
            self.scroll = max(0.0, self.scroll - direction * 48)
            return
        if self.overlay in ("pause", "reglages", "title"):
            self.spin += direction * 0.45
            return
        if self.overlay == "conseil" and self.council_phase == "orient":
            if not self._law_sliding():
                self.bump(1 if direction > 0 else -1)
            return
        if self.overlay == "courbes":
            self.read_pinned = True
            self.read_year = min(self.state.horizon, max(1900, self.read_at() + direction * 2))
            self.hear_year(self.read_year)
            return
        if self.overlay:
            return
        self.spin += direction * 0.45

    def on_key(self, key):
        if self.overlay == "title":
            if key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                self.dismiss_title()
            else:
                self._steer_planet(key)
            return
        if key == pygame.K_ESCAPE:
            if self.overlay == "confirm":
                self.cancel_reset()
            elif self.overlay == "intro":
                self.intro_next()
            elif self.overlay == "shock":
                self.dismiss_shock()
            elif self.overlay == "fiche":
                self.close_fiche()
            elif self.overlay == "pause":
                self.close_pause()
            elif self.overlay == "fin":
                self.close_fin()
            elif self.overlay in ("courbes", "reglages", "aide", "info"):
                self.close_panel()
            elif self.overlay is None:
                self.alive = False
            return
        if self.overlay in ("aide", "info", "fiche"):
            if key == pygame.K_UP:
                self.scroll = max(0.0, self.scroll - 48)
            elif key == pygame.K_DOWN:
                self.scroll += 48
            return
        if self.overlay == "conseil" and self.council_phase == "orient":
            if key == pygame.K_LEFT:
                self.shift_law(-1)
            elif key == pygame.K_RIGHT:
                self.shift_law(1)
            elif key == pygame.K_UP and not self._law_sliding():
                self.bump(1)
            elif key == pygame.K_DOWN and not self._law_sliding():
                self.bump(-1)
            return
        if self.overlay == "event":
            if self._event_sliding():
                return
            if key in (pygame.K_UP, pygame.K_LEFT):
                self.pick_choice("a")
            elif key in (pygame.K_DOWN, pygame.K_RIGHT):
                self.pick_choice("b")
            elif key in (pygame.K_RETURN, pygame.K_SPACE):
                self.validate_dilemma()
            return
        if self.overlay == "reglages" and self._steer_planet(key):
            return
        if self.overlay:
            return
        if self._steer_planet(key):
            return
        if key == pygame.K_SPACE:
            self.depart()

    def handle(self):
        if self.panel is not None:
            self.panel.poll()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.alive = False
            elif event.type == pygame.KEYDOWN:
                self.on_key(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.on_down(self.logical_pos(event.pos))
            elif event.type == pygame.MOUSEMOTION and self.down is not None:
                self.on_move(self.logical_pos(event.pos))
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.on_up(self.logical_pos(event.pos))
            elif event.type == pygame.MOUSEWHEEL:
                pos = self.logical_pos(getattr(event, "pos", (0, 0))) if hasattr(event, "pos") else (0, 0)
                self.on_wheel(pos, 1 if event.y > 0 else -1)

    def update(self, dt):
        poll_schedules()
        dt = min(float(dt), DT_MAX)
        paused = self.overlay is not None
        self.year_flash = max(0.0, self.year_flash - dt)
        self.seal_flash = max(0.0, self.seal_flash - dt)
        self.toast_t = max(0.0, self.toast_t - dt)
        self.beat += dt * DECOR_RATE
        if self.overlay == "conseil" or (self.overlay == "title" and self.title == "orient"):
            self._warm_council_edges()
        if self.overlay == "event" or (self.overlay == "title" and self.title == "dilemma"):
            self._warm_choices()
        if self.overlay == "shock":
            # Le balayage attend la courbe. Sinon il a déjà fini quand elle arrive.
            if self.shock_traj() is not None:
                if not self._shock_ready:
                    self.shock_sweep = 0.0
                    self._shock_ready = True
                self.shock_sweep += dt
            else:
                self._shock_ready = False
        if self.overlay == "title" and self.title == "event":
            cycle = math.floor((self.beat - self._wave_t0) * EVENT_WAVE)
            if self._event_wave_cycle is not None and cycle != self._event_wave_cycle:
                self.cue("warning")
            self._event_wave_cycle = cycle
        self._step_rockets(dt)
        self.talk_t += dt
        if self.talk_t > 3.2:
            self.talk_t = 0.0
            self.talk_i += 1
        self._advance_law_slide(dt)
        if self.overlay == "event":
            self._advance_event_slide(dt)
        target = self._law_notch()
        self.knob += (target - self.knob) * ease(16.0, dt)
        if self.turn_anim is not None and self.overlay is None:
            self._advance_turn(dt)
        self._step_stats(dt)
        if self.drag != "planet":
            self.yaw += self.spin * dt
            if self.turn_anim is not None and self.overlay is None:
                self.sat_yaw += self.spin * dt
                # Accel douce (~1,5 s pour atteindre ~95 % de TURN_SPIN).
                self.spin += (TURN_SPIN - self.spin) * ease(2.0, dt)
            else:
                mood = MOOD_SPIN.get(self.word_now(), -0.0375)
                self.sat_yaw += (self.spin - mood) * dt
                self.spin += (mood - self.spin) * ease(1.4, dt)
            self.pitch += self.pitch_spin * dt
            self.pitch_spin += (0.0 - self.pitch_spin) * ease(2.2, dt)
            if self.pitch < -PITCH_LIMIT:
                self.pitch = -PITCH_LIMIT
                self.pitch_spin = 0.0
            elif self.pitch > PITCH_LIMIT:
                self.pitch = PITCH_LIMIT
                self.pitch_spin = 0.0
        # Point de vue (Y) : offset par-dessus le spin, sans inertie integree.
        self._step_tilt(dt)
        if self.turn_anim is None and not paused:
            self.maybe_open()
        self.save_acc += dt
        if self.dirty and self.save_acc > 2 and not self.shots:
            self.state.save()
            self.dirty = False
            self.save_acc = 0

    def _step_tilt(self, dt):
        """Axe Y → offset de yaw. self.yaw tourne tout seul ; pas de vitesse ajoutée."""
        raw = self._tilt_key_yaw
        sensor = self.accel
        if sensor is not None:
            delta = sensor.read_y_delta()
            if delta is not None:
                if abs(delta) < TILT_Y_DEADZONE:
                    delta = 0.0
                raw += delta
        # Double lissage : coupe les a-coups sans integrer de vitesse.
        self._y_smooth += (raw - self._y_smooth) * ease(TILT_Y_SMOOTH, dt)
        self._y_smooth2 += (self._y_smooth - self._y_smooth2) * ease(TILT_Y_SMOOTH2, dt)
        self.tilt_yaw = max(-TILT_YAW_MAX, min(TILT_YAW_MAX, self._y_smooth2 * TILT_Y_GAIN))

    def _step_rockets(self, dt):
        """Un décollage de temps en temps, seulement si l'industrie est haute."""
        kept = []
        for rocket in self.rockets:
            rocket["t"] += dt / rocket["dur"]
            if rocket["t"] < 1.0:
                kept.append(rocket)
        self.rockets = kept
        if self.overlay is not None or self.rockets:
            return
        goods = self.traj().sample(self.shown_year())["iopc"]
        if goods < 220:
            return
        span = min(1.0, (goods - 220) / 260)
        mean = 18.0 - 10.0 * span
        if random.random() < dt / mean:
            self.rockets.append(
                {
                    "ang": random.random() * math.tau,
                    "bend": (random.random() * 2.0 - 1.0) * 0.55,
                    "seed": random.randrange(1 << 30),
                    "t": 0.0,
                    "dur": 2.6 + random.random() * 0.9,
                }
            )

    def frame(self):
        self.hits = draw(self.surf, self.font, self)

    def run(self):
        if not self.shots and os.environ.get("WORLD3_PACE", "1") != "0":
            from pathlib import Path

            from .pace import Pace

            root = Path(__file__).resolve().parent.parent
            self.pace = Pace(root / "pace.log")
            if self.pace.fh is not None:
                print(f"Rythme : {self.pace.path}", flush=True)
        try:
            self.boot()
            self.maybe_open()
            clock = pygame.time.Clock()
            dt = 0.0
            while self.alive:
                t0 = time.perf_counter()
                self.handle()
                handle_ms = (time.perf_counter() - t0) * 1000.0
                t1 = time.perf_counter()
                self.update(dt)
                update_ms = (time.perf_counter() - t1) * 1000.0
                t2 = time.perf_counter()
                self.frame()
                draw_ms = (time.perf_counter() - t2) * 1000.0
                t3 = time.perf_counter()
                self.present()
                present_ms = (time.perf_counter() - t3) * 1000.0
                work_ms = (time.perf_counter() - t0) * 1000.0
                tick_ms = clock.tick(30)
                if self.pace is not None:
                    self.pace.frame(
                        self._pace_page(), self._pace_act(), self.state.year,
                        work_ms, tick_ms, handle_ms, update_ms, draw_ms, present_ms,
                    )
                dt = tick_ms / 1000.0
            if not self.shots:
                self.state.save()
        finally:
            close_schedules()
            if self.pace is not None:
                self.pace.close()
                self.pace = None
            if self.accel is not None:
                self.accel.close()
                self.accel = None

    def shoot(self, path):
        self.frame()
        path.parent.mkdir(parents=True, exist_ok=True)
        pygame.image.save(self.surf, str(path))


def gallery(app, folder):
    app.overlay = "intro"
    app.intro_i = 0
    app.shoot(folder / "01_intro.png")
    app.state.seen_intro = True
    app.overlay = None
    app.screen = "monde"
    app.state.year = 2026
    app.shoot(folder / "02_monde.png")
    app.overlay = "pause"
    app.shoot(folder / "03_pause.png")
    app.overlay = "conseil"
    app.council_phase = "orient"
    app.state.seals = MAX_SEALS
    app.state.year = 2030
    app.law = 4
    app.knob = 0
    app.preview = None
    app.shoot(folder / "04_conseil.png")
    app.overlay = "event"
    app.event = EVENTS[0]
    app.shoot(folder / "05_dilemme.png")
    spec = SHOCK_BY_ID["iag"]
    app.overlay = "shock"
    app.state.year = 2031
    app.shock = {
        "id": spec["id"],
        "year": 2031,
        "title": spec["title"],
        "lines": spec["lines"],
        "effect": spec.get("effect") or "",
        "info": card_info(spec),
    }
    app.shoot(folder / "10_evenement.png")
    app.shock = None
    app.state.year = 2030
    app.overlay = "courbes"
    app.shoot(folder / "06_courbes.png")
    app.overlay = "reglages"
    app.shoot(folder / "07_reglages.png")
    app.overlay = "title"
    app.title = "orient"
    app.state.year = 2030
    app.shoot(folder / "09_titre_conseil.png")
    app.title = "event"
    app.shoot(folder / "11_titre_event.png")
    app.title = "dilemma"
    app.shoot(folder / "12_titre_dilemme.png")
    app.overlay = "fin"
    app.fin_kind = "chute"
    app.fin_word = "FAMINE"
    app.fin_can = False
    app._fin_copy = FIN["chute"]
    app.state.year = 2100
    app.shoot(folder / "08_fin.png")


def run_game(screen, save_path):
    """Partie sur un ecran deja ouvert. Retourne quand on quitte le globe."""
    from .font import Font

    font = Font()
    state = GameState(save_path)
    state.load()
    app = App(screen.surf, screen.window, font, state, panel=screen.panel)
    app.run()
    return app


def main(argv=None):
    import argparse
    import tempfile
    from pathlib import Path

    from .font import Font

    parser = argparse.ArgumentParser(description="WORLD3, une planete a tenir.")
    parser.add_argument("--fullscreen", action="store_true")
    parser.add_argument("--scale", type=int, default=1)
    parser.add_argument("--shots", action="store_true")
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parent.parent
    if args.shots:
        save_path = Path(tempfile.gettempdir()) / "world3_shots.json"
        if save_path.exists():
            save_path.unlink()
    else:
        save_path = root / "save.json"

    screen = open_screen(args.fullscreen, args.scale, "WORLD3")
    try:
        if args.shots:
            font = Font()
            state = GameState(save_path)
            app = App(
                screen.surf, screen.window, font, state,
                shots=True, panel=screen.panel,
            )
            app.boot()
            gallery(app, root / "shots")
        else:
            run_game(screen, save_path)
    finally:
        screen.close()


if __name__ == "__main__":
    main()
