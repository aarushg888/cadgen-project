"""Build automated-quality benchmark v1: template-generated, machine-verified.

Why templates, not the LLM-synth path (AGENTS.md 3.1-2): 300 candidates at ~45s
each is ~4h of sequential local generation for a ~15% end-to-end yield, and the
zero-shot baseline showed local code quality is poor (exec 0.33). Templates emit
exact (prompt, code, expected-geometry) triples in seconds; every candidate still
passes the full gate chain below, so v1 is verified, not merely asserted.

Gates (all real, all run):
  1. sandbox execution -> valid single solid (cadgen.data.filter, dedupe on)
  2. self-consistency: prompt-stated dims == executed bbox (bbox_match 10%) and
     executed volume == analytic volume (25%). Templates carry expected geometry.
  3. decontamination vs pilot train: prompt near-dup (normalized-exact or token
     Jaccard >= 0.85) or geometry-signature match -> reject.

Output: benchmark/tasks.jsonl [{id, prompt, code, category, tier}], report.json.
This is an AUTOMATED-QUALITY benchmark (no hand verification); the human
spot-check fraction is recorded separately in STATUS.md, not claimed here.

    python benchmark/build_v1.py --n-per-tier 100 --seed 7
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import tempfile

from cadgen.data.filter import _geom_sig, run_filter
from cadgen.metrics import bbox_match, volume_match
from cadgen.schema import read_jsonl
from types import SimpleNamespace

ROOT = os.path.join(os.path.dirname(__file__))
PI = math.pi


# ---------------------------------------------------------------- emitters
# Each emitter(rng, style) -> dict(prompt, code, category, expected_bbox, expected_vol).
# expected_bbox = true [x, y, z] extents in mm; expected_vol = analytic volume.
# Only well-trodden ops: box/circle/extrude/rect/polygon/hole/cut/shell/polarArray/union.

def _p(style, plain, casual, spec, minimal):
    return {"plain": plain, "casual": casual, "spec": spec, "minimal": minimal}[style]


def _ri(rng, lo, hi):
    """randint with ordered bounds (guards against empty ranges)."""
    lo, hi = int(lo), int(hi)
    if hi < lo:
        hi = lo
    return rng.randint(lo, hi)


def plate_holes(rng, style, wide=False):
    if wide:
        L, W, T = _ri(rng, 30, 150), _ri(rng, 20, 100), _ri(rng, 3, 12)
        e = _ri(rng, 4, min(12, L // 2 - 2, W // 2 - 2))
        d = _ri(rng, 3, min(10, 2 * e - 1))
    else:
        L, W, T = rng.choice([40, 50, 60, 80]), rng.choice([30, 40, 50]), rng.choice([4, 5, 6, 8])
        d, e = rng.choice([3, 4, 5, 6]), rng.choice([4, 5, 6])
    prompt = _p(style,
        f"A rectangular mounting plate {L} mm by {W} mm and {T} mm thick with four {d} mm diameter holes, one near each corner, {e} mm in from each edge.",
        f"hey, i need a mounting plate about {L}x{W} mm, {T} mm thick, with 4 holes ({d} mm dia) near the corners, {e} mm in from the edges.",
        f"MOUNTING PLATE\nOuter: {L} x {W} x {T} mm\nHoles: 4x dia {d} mm, {e} mm edge inset",
        f"{L}x{W}x{T} plate, four {d}mm corner holes ({e}mm inset).")
    code = (f"import cadquery as cq\nresult = (cq.Workplane(\"XY\").box({L}, {W}, {T}).faces(\">Z\").workplane()\n"
            f"          .rect({L - 2 * e}, {W - 2 * e}, forConstruction=True).vertices().hole({d}))\n")
    return dict(prompt=prompt, code=code, category="mechanical",
                expected_bbox=[L, W, T], expected_vol=L * W * T - 4 * PI * (d / 2) ** 2 * T)


def cylinder(rng, style, wide=False):
    if wide:
        D, H = _ri(rng, 10, 100), _ri(rng, 10, 200)
    else:
        D, H = rng.choice([20, 25, 30, 40, 50]), rng.choice([30, 40, 50, 60, 80])
    prompt = _p(style,
        f"A solid cylinder {D} mm in diameter and {H} mm tall.",
        f"can you make a plain cylinder, {D} mm across and {H} mm tall?",
        f"CYLINDER\nDiameter: {D} mm\nHeight: {H} mm",
        f"cylinder {D} dia x {H}.")
    code = f"import cadquery as cq\nresult = cq.Workplane(\"XY\").circle({D / 2}).extrude({H})\n"
    return dict(prompt=prompt, code=code, category="mechanical",
                expected_bbox=[D, D, H], expected_vol=PI * (D / 2) ** 2 * H)


def washer(rng, style, wide=False):
    if wide:
        OD, t = _ri(rng, 12, 60), _ri(rng, 1, 6)
    else:
        OD, t = rng.choice([16, 20, 24, 30]), rng.choice([1.5, 2, 2.5, 3])
    ID = OD // 2
    prompt = _p(style,
        f"A flat washer with {OD} mm outer diameter, {ID} mm inner diameter and {t} mm thickness.",
        f"just a flat washer: {OD} mm outside, {ID} mm hole, {t} mm thick.",
        f"WASHER\nOD: {OD} mm\nID: {ID} mm\nThickness: {t} mm",
        f"washer {OD}/{ID}x{t}.")
    code = f"import cadquery as cq\nresult = cq.Workplane(\"XY\").circle({OD / 2}).circle({ID / 2}).extrude({t})\n"
    return dict(prompt=prompt, code=code, category="mechanical",
                expected_bbox=[OD, OD, t], expected_vol=PI * ((OD / 2) ** 2 - (ID / 2) ** 2) * t)


def hex_nut(rng, style, wide=False):
    if wide:
        AF, t = _ri(rng, 8, 30), _ri(rng, 4, 16)
    else:
        AF, t = rng.choice([11, 13, 14, 17, 19]), rng.choice([5, 6, 8, 10])
    d = AF // 2 + 1
    flats = round(AF * math.sqrt(3) / 2, 4)  # polygon() circumscribes: AF is across corners
    prompt = _p(style,
        f"A hexagonal nut, {AF} mm across the corners, {t} mm thick, with a {d} mm diameter center hole.",
        f"a hex nut about {AF} mm across the corners, {t} mm thick, hole {d} mm.",
        f"HEX NUT\nAcross corners: {AF} mm\nThickness: {t} mm\nHole: dia {d} mm",
        f"hex nut {AF} AF x {t}, {d}mm hole.")
    code = (f"import cadquery as cq\nresult = cq.Workplane(\"XY\").polygon(6, {AF}).circle({d / 2}).extrude({t})\n")
    return dict(prompt=prompt, code=code, category="mechanical",
                expected_bbox=[AF, flats, t], expected_vol=(0.6495 * AF * AF - PI * (d / 2) ** 2) * t)


def disc_holes(rng, style, wide=False):
    if wide:
        D, t = _ri(rng, 60, 150), _ri(rng, 3, 12)
        n, dh = _ri(rng, 3, 8), _ri(rng, 3, 8)
        dc = _ri(rng, 2 * (5 + dh // 2 + 1), D - 4 - dh)
    else:
        D, t = rng.choice([50, 60, 80]), rng.choice([5, 6, 8])
        n, dh, dc = rng.choice([4, 6, 8]), rng.choice([4, 5, 6]), D // 2 - 10
    prompt = _p(style,
        f"A round disc {D} mm in diameter and {t} mm thick with a 10 mm center hole and {n} {dh} mm holes evenly spaced on a {dc} mm diameter circle.",
        f"round disc {D} mm x {t} mm, center hole 10 mm plus {n} holes of {dh} mm on a {dc} mm circle.",
        f"DISC\nDia {D} mm x {t} mm\nCenter hole: 10 mm\nBolt circle: {n}x dia {dh} mm on dia {dc} mm",
        f"disc {D}x{t}, 10mm center + {n}x{dh}mm on {dc}mm circle.")
    code = (f"import cadquery as cq\nresult = (cq.Workplane(\"XY\").circle({D / 2}).extrude({t})"
            f".faces(\">Z\").workplane().hole(10)\n"
            f"          .faces(\">Z\").workplane().polarArray({dc / 2}, 0, 360, {n}).hole({dh}))\n")
    vol = PI * (D / 2) ** 2 * t - PI * 5 ** 2 * t - n * PI * (dh / 2) ** 2 * t
    return dict(prompt=prompt, code=code, category="mechanical",
                expected_bbox=[D, D, t], expected_vol=vol)


def l_bracket(rng, style, wide=False):
    if wide:
        A, B, th, W = _ri(rng, 20, 100), _ri(rng, 20, 100), _ri(rng, 2, 8), _ri(rng, 10, 50)
        th = min(th, A // 2, B // 2)
    else:
        A, B, th, W = rng.choice([30, 40, 50]), rng.choice([30, 40, 50]), rng.choice([3, 4, 5]), rng.choice([15, 20, 25])
    prompt = _p(style,
        f"An L-shaped bracket: one leg {A} mm long, the other {B} mm long, {th} mm thick and {W} mm wide, joined at a right angle.",
        f"an L bracket, legs {A} and {B} mm, {th} mm thick, {W} mm wide.",
        f"L-BRACKET\nLeg 1: {A} mm\nLeg 2: {B} mm\nThickness: {th} mm\nWidth: {W} mm",
        f"L-bracket {A}x{B}x{th}, width {W}.")
    code = (f"import cadquery as cq\nresult = cq.Workplane(\"XZ\").polyline([(0,0),({A},0),({A},{th}),({th},{th}),"
            f"({th},{B}),(0,{B})]).close().extrude({W})\n")
    return dict(prompt=prompt, code=code, category="mechanical",
                expected_bbox=[A, B, W], expected_vol=(A * th + (B - th) * th) * W)


def u_channel(rng, style, wide=False):
    if wide:
        L, W, H, t = _ri(rng, 20, 120), _ri(rng, 10, 60), _ri(rng, 8, 40), _ri(rng, 1, 4)
        t = min(t, W // 2 - 1, H - 1)
    else:
        L, W, H, t = rng.choice([40, 50, 60]), rng.choice([20, 24, 30]), rng.choice([12, 15, 20]), 2
    prompt = _p(style,
        f"A U-shaped channel {L} mm long with a {W} mm wide, {H} mm tall cross-section and {t} mm thick walls and base.",
        f"u-channel, {L} mm long, {W}x{H} cross-section, {t} mm walls.",
        f"U-CHANNEL\nLength: {L} mm\nWidth: {W} mm\nHeight: {H} mm\nWall: {t} mm",
        f"u-channel {L} long, {W}x{H}, {t}mm wall.")
    code = (f"import cadquery as cq\nresult = cq.Workplane(\"XY\").polyline([(0,0),({W},0),({W},{H}),({W - t},{H}),"
            f"({W - t},{t}),({t},{t}),({t},{H}),(0,{H})]).close().extrude({L})\n")
    return dict(prompt=prompt, code=code, category="mechanical",
                expected_bbox=[W, H, L], expected_vol=(W * H - (W - 2 * t) * (H - t)) * L)


def open_box(rng, style, wide=False):
    if wide:
        L, W, H, t = _ri(rng, 30, 200), _ri(rng, 30, 200), _ri(rng, 15, 100), _ri(rng, 1, 5)
        t = min(t, L // 2 - 1, W // 2 - 1)
    else:
        L, W, H, t = rng.choice([60, 80, 100]), rng.choice([40, 50, 60]), rng.choice([25, 30, 40]), 2
    prompt = _p(style,
        f"A rectangular open-top box, {L} mm long, {W} mm wide and {H} mm tall, with {t} mm thick walls.",
        f"open-top box {L}x{W}x{H} mm, walls {t} mm.",
        f"OPEN BOX\nOuter: {L} x {W} x {H} mm\nWall: {t} mm",
        f"open box {L}x{W}x{H}, {t}mm walls.")
    code = f"import cadquery as cq\nresult = cq.Workplane(\"XY\").box({L}, {W}, {H}).faces(\">Z\").shell(-{t})\n"
    return dict(prompt=prompt, code=code, category="mechanical",
                expected_bbox=[L, W, H], expected_vol=L * W * H - (L - 2 * t) * (W - 2 * t) * (H - t))


def flange(rng, style, wide=False):
    if wide:
        Rb, tb = _ri(rng, 15, 60), _ri(rng, 4, 15)
        Rh = _ri(rng, max(6, int(Rb * 0.4)), max(7, int(Rb * 0.7)))
        hh, d = _ri(rng, 8, 40), None
        d = _ri(rng, 4, max(5, 2 * Rh - 4))
    else:
        Rb, tb = rng.choice([25, 30, 40]), rng.choice([6, 8, 10])
        Rh, hh, d = Rb // 2, rng.choice([15, 20, 25]), rng.choice([8, 10, 12])
    prompt = _p(style,
        f"A flange: a {2 * Rb} mm diameter base {tb} mm thick with a {2 * Rh} mm diameter hub {hh} mm tall and a {d} mm center bore through both.",
        f"flange, base {2 * Rb}x{tb} mm, hub {2 * Rh} dia x {hh} tall, {d} mm bore.",
        f"FLANGE\nBase: dia {2 * Rb} x {tb} mm\nHub: dia {2 * Rh} x {hh} mm\nBore: {d} mm",
        f"flange {2 * Rb}/{2 * Rh}x{tb}+{hh}, bore {d}.")
    code = (f"import cadquery as cq\nresult = (cq.Workplane(\"XY\").circle({Rb}).extrude({tb})"
            f".faces(\">Z\").workplane().circle({Rh}).extrude({hh})"
            f".faces(\">Z\").workplane().hole({d}))\n")
    vol = PI * Rb ** 2 * tb + PI * Rh ** 2 * hh - PI * (d / 2) ** 2 * (tb + hh)
    return dict(prompt=prompt, code=code, category="mechanical",
                expected_bbox=[2 * Rb, 2 * Rb, tb + hh], expected_vol=vol)


def standoff(rng, style, wide=False):
    if wide:
        AF, h = _ri(rng, 6, 20), _ri(rng, 6, 40)
        d = _ri(rng, 2, max(3, int(AF * 0.8)))
    else:
        AF, h, d = rng.choice([8, 10, 12]), rng.choice([10, 15, 20, 25]), rng.choice([3, 4, 5])
    flats = round(AF * math.sqrt(3) / 2, 4)
    prompt = _p(style,
        f"A hexagonal standoff, {AF} mm across the corners, {h} mm tall, with a {d} mm through hole.",
        f"hex standoff {AF} mm across the corners, {h} tall, {d} mm hole.",
        f"STANDOFF\nAcross corners: {AF} mm\nHeight: {h} mm\nHole: {d} mm",
        f"hex standoff {AF}x{h}, hole {d}.")
    code = f"import cadquery as cq\nresult = cq.Workplane(\"XY\").polygon(6, {AF}).circle({d / 2}).extrude({h})\n"
    return dict(prompt=prompt, code=code, category="mechanical",
                expected_bbox=[AF, flats, h], expected_vol=(0.6495 * AF * AF - PI * (d / 2) ** 2) * h)


def pencil_holder(rng, style, wide=False):
    if wide:
        R, h = _ri(rng, 20, 60), _ri(rng, 40, 160)
        wt, bt = _ri(rng, 3, 8), _ri(rng, 3, 10)
        wt = min(wt, R // 2 - 1)
    else:
        R, h = rng.choice([35, 40, 45]), rng.choice([80, 100, 120])
        wt, bt = 5, 5
    prompt = _p(style,
        f"A round pencil holder {2 * R} mm in diameter and {h} mm tall, hollow with {wt} mm thick walls and a {bt} mm thick solid base.",
        f"pencil cup, {2 * R} mm round, {h} tall, {wt} mm walls.",
        f"PENCIL HOLDER\nOD: {2 * R} mm\nHeight: {h} mm\nWall/base: {wt}/{bt} mm",
        f"pencil holder {2 * R} dia x {h}.")
    code = (f"import cadquery as cq\nouter = cq.Workplane(\"XY\").circle({R}).extrude({h})\n"
            f"inner = cq.Workplane(\"XY\").workplane(offset={bt}).circle({R - wt}).extrude({h - bt})\n"
            f"result = outer.cut(inner)\n")
    vol = PI * R ** 2 * h - PI * (R - wt) ** 2 * (h - bt)
    return dict(prompt=prompt, code=code, category="consumer",
                expected_bbox=[2 * R, 2 * R, h], expected_vol=vol)


def picture_frame(rng, style, wide=False):
    if wide:
        L, W = _ri(rng, 80, 300), None
        W, b, t = _ri(rng, 60, 250), None, _ri(rng, 3, 15)
        W = min(W, L - 10)
        b = _ri(rng, 8, min(30, min(L, W) // 2 - 5))
    else:
        L, W, b, t = rng.choice([150, 200]), rng.choice([100, 120, 150]), rng.choice([12, 15, 20]), rng.choice([6, 8, 10])
    prompt = _p(style,
        f"A flat rectangular picture frame, {L} mm by {W} mm outside, with a {b} mm wide border and {t} mm thickness (open in the middle).",
        f"picture frame {L}x{W} mm, {b} mm border, {t} thick, open middle.",
        f"FRAME\nOuter: {L} x {W} mm\nBorder: {b} mm\nThk: {t} mm (open)",
        f"frame {L}x{W}, border {b}, thk {t}.")
    code = f"import cadquery as cq\nresult = cq.Workplane(\"XY\").rect({L}, {W}).rect({L - 2 * b}, {W - 2 * b}).extrude({t})\n"
    return dict(prompt=prompt, code=code, category="consumer",
                expected_bbox=[L, W, t], expected_vol=(L * W - (L - 2 * b) * (W - 2 * b)) * t)


def square_planter(rng, style, wide=False):
    if wide:
        L, h = _ri(rng, 60, 250), _ri(rng, 60, 250)
        wt, bt = _ri(rng, 3, 10), _ri(rng, 5, 15)
        wt = min(wt, L // 2 - 2)
    else:
        L, h = rng.choice([120, 150, 180]), rng.choice([120, 150, 200])
        wt, bt = rng.choice([4, 5, 6]), 8
    prompt = _p(style,
        f"A square planter pot, {L} mm by {L} mm and {h} mm tall, with {wt} mm thick walls and an {bt} mm thick base, open at the top.",
        f"square planter {L}x{L}x{h} mm, {wt} mm walls.",
        f"PLANTER\nOuter: {L} x {L} x {h} mm\nWall: {wt} mm\nBase: {bt} mm",
        f"planter {L}x{L}x{h}, wall {wt}.")
    code = (f"import cadquery as cq\nouter = cq.Workplane(\"XY\").box({L}, {L}, {h})\n"
            f"inner = cq.Workplane(\"XY\").box({L - 2 * wt}, {L - 2 * wt}, {h - bt}).translate((0, 0, {bt / 2}))\n"
            f"result = outer.cut(inner)\n")
    vol = L * L * h - (L - 2 * wt) ** 2 * (h - bt)
    return dict(prompt=prompt, code=code, category="consumer",
                expected_bbox=[L, L, h], expected_vol=vol)


def drain_coaster(rng, style, wide=False):
    if wide:
        D, t = _ri(rng, 60, 150), _ri(rng, 4, 12)
        n, dh = _ri(rng, 3, 8), _ri(rng, 3, 8)
        dc = _ri(rng, 2 * dh, max(2 * dh, D - dh - 4))
    else:
        D, t = rng.choice([90, 100, 110]), rng.choice([6, 8])
        n, dh = 6, 5
        dc = D - 30
    prompt = _p(style,
        f"A round drink coaster {D} mm in diameter and {t} mm thick with {n} {dh} mm drainage holes evenly spaced on a {dc} mm diameter circle.",
        f"coaster {D} mm, {t} thick, {n} drain holes {dh} mm on {dc} mm circle.",
        f"COASTER\nDia {D} x {t} mm\nDrains: {n}x dia {dh} mm on dia {dc} mm",
        f"coaster {D}x{t}, {n}x{dh} drains.")
    code = (f"import cadquery as cq\nresult = (cq.Workplane(\"XY\").circle({D / 2}).extrude({t})"
            f".faces(\">Z\").workplane().polarArray({dc / 2}, 0, 360, {n}).hole({dh}))\n")
    vol = PI * (D / 2) ** 2 * t - n * PI * (dh / 2) ** 2 * t
    return dict(prompt=prompt, code=code, category="consumer",
                expected_bbox=[D, D, t], expected_vol=vol)


def bookend(rng, style, wide=False):
    if wide:
        L, D, H, t = _ri(rng, 80, 200), _ri(rng, 60, 160), _ri(rng, 80, 220), _ri(rng, 2, 8)
    else:
        L, D, H = rng.choice([120, 140]), rng.choice([100, 120]), rng.choice([140, 160])
        t = 4
    prompt = _p(style,
        f"An L-shaped metal bookend: a {L} mm by {D} mm base and a {H} mm tall back, both {t} mm thick.",
        f"bookend, base {L}x{D} mm, back {H} tall, {t} mm thick.",
        f"BOOKEND\nBase: {L} x {D} mm\nBack height: {H} mm\nStock: {t} mm",
        f"bookend {L}x{D}x{H}, {t}mm.")
    code = (f"import cadquery as cq\nbase = cq.Workplane(\"XY\").box({L}, {D}, {t})\n"
            f"back = cq.Workplane(\"XY\").box({L}, {t}, {H}).translate((0, {D / 2 - t / 2}, {H / 2 - t / 2}))\n"
            f"result = base.union(back)\n")
    vol = L * D * t + L * t * H - L * t * t  # overlap counted once
    return dict(prompt=prompt, code=code, category="consumer",
                expected_bbox=[L, D, H], expected_vol=vol)


def simple_table(rng, style, wide=False):
    if wide:
        L, W = _ri(rng, 300, 1200), _ri(rng, 200, 800)
        T, leg, legH = _ri(rng, 15, 40), None, _ri(rng, 200, 800)
        leg = _ri(rng, 30, min(80, L // 2 - 10, W // 2 - 10))
    else:
        L, W = rng.choice([600, 800]), rng.choice([400, 500])
        T, leg, legH = 25, 50, rng.choice([400, 500, 700])
    ix, iy = L / 2 - leg, W / 2 - leg
    prompt = _p(style,
        f"A simple rectangular side table: a {L} mm by {W} mm top, {T} mm thick, on four {leg} mm square legs {legH} mm tall (top surface {legH + T} mm off the floor).",
        f"small table {L}x{W} mm top ({T} thick), 4 legs {leg}x{leg}x{legH}.",
        f"TABLE\nTop: {L} x {W} x {T} mm\nLegs: 4x {leg} x {leg} x {legH} mm",
        f"table {L}x{W}x{T} top, legs {leg}x{legH}.")
    code = (f"import cadquery as cq\ntop = cq.Workplane(\"XY\").box({L}, {W}, {T}).translate((0, 0, {legH + T / 2}))\n"
            f"leg = cq.Workplane(\"XY\").box({leg}, {leg}, {legH + 1}).translate((0, 0, {(legH + 1) / 2}))\n"
            f"result = top.union(leg.translate(({ix}, {iy}, 0))).union(leg.translate(({-ix}, {iy}, 0)))"
            f".union(leg.translate(({ix}, {-iy}, 0))).union(leg.translate(({-ix}, {-iy}, 0)))\n")
    vol = L * W * T + 4 * leg * leg * legH
    return dict(prompt=prompt, code=code, category="architectural",
                expected_bbox=[L, W, legH + T], expected_vol=vol)


def shelf_unit(rng, style, wide=False):
    if wide:
        W, D, H = _ri(rng, 300, 1200), _ri(rng, 150, 500), _ri(rng, 400, 2000)
        t, n = _ri(rng, 10, 25), _ri(rng, 2, 5)
        t = min(t, (W - 20) // 2, H // (n + 1) - 4)
    else:
        W, D, H = rng.choice([600, 800]), rng.choice([250, 300]), rng.choice([900, 1200])
        t, n = 18, rng.choice([3, 4])
    prompt = _p(style,
        f"A simple open shelf unit {W} mm wide, {D} mm deep and {H} mm tall: two {t} mm side panels with {n} {t} mm shelves between them.",
        f"shelf unit {W}x{D}x{H} mm, sides + {n} shelves, {t} mm stock.",
        f"SHELF\nW {W} x D {D} x H {H} mm\nSides/shelves: {t} mm\nShelves: {n}",
        f"shelf {W}x{D}x{H}, {n} shelves.")
    shelves = "cq.Workplane(\"XY\").box(%s, %s, %s)" % (W - 2 * t, D, t)
    shelves += "".join(".union(cq.Workplane(\"XY\").box(%s, %s, %s).translate((0, 0, %s)))" % (W - 2 * t, D, t, h)
                       for h in [round(H * (i + 1) / (n + 1)) for i in range(n)])
    code = (f"import cadquery as cq\nside = cq.Workplane(\"XY\").box({t}, {D}, {H}).translate((0, 0, {H / 2}))\n"
            f"sides = side.translate(({-W / 2 + t / 2}, 0, 0)).union(side.translate(({W / 2 - t / 2}, 0, 0)))\n"
            f"shelf = ({shelves})\n"
            f"result = sides.union(shelf)\n")
    vol = 2 * t * D * H + n * (W - 2 * t) * D * t
    return dict(prompt=prompt, code=code, category="architectural",
                expected_bbox=[W, D, H], expected_vol=vol)


def stepped_vase(rng, style, wide=False):
    if wide:
        R0 = _ri(rng, 20, 80)
        hs = [_ri(rng, 20, 100) for _ in range(3)]
    else:
        R0 = rng.choice([40, 50])
        hs = [rng.choice([40, 50, 60]) for _ in range(3)]
    Rs = [R0, max(5, round(R0 * 0.75)), max(3, round(R0 * 0.5))]
    H = sum(hs)
    prompt = _p(style,
        f"A stepped cylindrical vase of three stacked sections with radii {Rs[0]}, {Rs[1]} and {Rs[2]} mm and heights {hs[0]}, {hs[1]} and {hs[2]} mm.",
        f"stepped vase, radii {Rs[0]}/{Rs[1]}/{Rs[2]} mm, heights {hs[0]}/{hs[1]}/{hs[2]}.",
        f"VASE (stepped)\nR: {Rs[0]} / {Rs[1]} / {Rs[2]} mm\nH: {hs[0]} / {hs[1]} / {hs[2]} mm",
        f"stepped vase R{Rs[0]}/{Rs[1]}/{Rs[2]} H{hs[0]}/{hs[1]}/{hs[2]}.")
    code = (f"import cadquery as cq\nresult = (cq.Workplane(\"XY\").circle({Rs[0]}).extrude({hs[0]})"
            f".faces(\">Z\").workplane().circle({Rs[1]}).extrude({hs[1]})"
            f".faces(\">Z\").workplane().circle({Rs[2]}).extrude({hs[2]}))\n")
    vol = sum(PI * r ** 2 * h for r, h in zip(Rs, hs))
    return dict(prompt=prompt, code=code, category="architectural",
                expected_bbox=[2 * R0, 2 * R0, H], expected_vol=vol)


TIER1 = [plate_holes, cylinder, washer, hex_nut, disc_holes, l_bracket, u_channel, open_box, flange, standoff]
TIER3 = [pencil_holder, picture_frame, square_planter, drain_coaster, bookend, simple_table, shelf_unit, stepped_vase]
STYLES1 = ["plain"]
STYLES2 = ["casual", "spec", "minimal"]
STYLES3 = ["plain", "casual", "spec", "minimal"]


# ---------------------------------------------------------------- gates
def _norm_prompt(p):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", p.lower())).strip()


def _tok_jaccard(a, b):
    sa, sb = set(a.split()), set(b.split())
    return len(sa & sb) / max(1, len(sa | sb))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-per-tier", type=int, default=100)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--wide", action="store_true",
                    help="wide dimension ranges (training supplement; benchmark stays narrow for reproducibility)")
    ap.add_argument("--train", default="data/splits/pilot/train.jsonl")
    ap.add_argument("--out", default="benchmark/tasks.jsonl")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    rng = random.Random(a.seed)

    cands, meta = [], {}
    plan = [(1, TIER1, STYLES1), (2, TIER1, STYLES2), (3, TIER3, STYLES3)]
    cid = 0
    for tier, fns, styles in plan:
        for _ in range(a.n_per_tier):
            fn, style = rng.choice(fns), rng.choice(styles)
            try:
                e = fn(rng, style, wide=a.wide)
                compile(e["code"], "<bench>", "exec")  # fail fast with template name attached
            except Exception as ex:
                print("emit skip:", fn.__name__, repr(ex)[:100])
                continue
            cid += 1
            cands.append({"id": f"bench-{tier}-{cid:03d}", "prompt": e["prompt"], "code": e["code"],
                          "source": "bench-v1", "license": "own", "group": f"bench:{fn.__name__}:{cid}",
                          "tier": tier, "category": e["category"]})
            meta[cands[-1]["id"]] = (e["expected_bbox"], e["expected_vol"], fn.__name__, style)
    tmp = tempfile.mkdtemp(prefix="benchfilter_")
    with open(os.path.join(tmp, "cands.jsonl"), "w") as f:
        for c in cands:
            f.write(json.dumps({k: c[k] for k in ("id", "prompt", "code", "source", "license", "group")}) + "\n")
    stats = run_filter(os.path.join(tmp, "cands.jsonl"), os.path.join(tmp, "f"), workers=a.workers,
                       dedupe_code=True, dedupe_geom=True)
    print("gate1 exec:", json.dumps(stats["counts"]))
    passed = {json.loads(l)["id"]: json.loads(l) for l in open(os.path.join(tmp, "f", "passed.jsonl"))}

    # gate 2: self-consistency (prompt dims == executed geometry)
    from collections import Counter
    consistent = {}
    gate2reject = Counter()
    for pid, row in passed.items():
        exp_bbox, exp_vol, fn_name, style = meta[pid]
        ex = row["meta"]["exec"]
        if bbox_match(exp_bbox, ex["bbox"], tol=0.10) and volume_match(ex["volume"], exp_vol, tol=0.25):
            consistent[pid] = row
        else:
            gate2reject[fn_name] += 1
    print(f"gate2 consistency: {len(consistent)}/{len(passed)} reject-by-template: {dict(gate2reject)}")

    # gate 3: decontaminate vs pilot train
    train = list(read_jsonl(a.train))
    train_prompts = [_norm_prompt(t["prompt"]) for t in train]
    train_sig = set()
    for t in train:
        ex = (t.get("meta") or {}).get("exec")
        if ex:
            train_sig.add(_geom_sig(SimpleNamespace(volume=ex["volume"], bbox=ex["bbox"], n_faces=ex["n_faces"])))
    tasks, report = [], {"gate1": stats["counts"], "gate2kept": len(consistent), "reject": []}
    for pid, row in consistent.items():
        np_ = _norm_prompt(row["prompt"])
        if np_ in train_prompts:
            report["reject"].append((pid, "prompt-exact")); continue
        if max((_tok_jaccard(np_, tp) for tp in train_prompts), default=0) >= 0.85:
            report["reject"].append((pid, "prompt-jaccard")); continue
        ex = row["meta"]["exec"]
        if _geom_sig(SimpleNamespace(volume=ex["volume"], bbox=ex["bbox"], n_faces=ex["n_faces"])) in train_sig:
            report["reject"].append((pid, "geom")); continue
        c = next(c for c in cands if c["id"] == pid)
        tasks.append({"id": pid, "prompt": c["prompt"], "code": c["code"],
                      "category": c["category"], "tier": c["tier"]})
    from collections import Counter
    report["final"] = len(tasks)
    report["per_tier"] = dict(Counter(t["tier"] for t in tasks))
    report["per_template"] = dict(Counter(meta[t["id"]][2] for t in tasks))
    with open(a.out, "w") as f:
        for t in tasks:
            f.write(json.dumps(t) + "\n")
    with open(os.path.join(ROOT, "report.json"), "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps({k: v for k, v in report.items() if k != "reject"}, indent=2))
    print("spotcheck:", random.Random(a.seed + 1).sample([t["id"] for t in tasks], min(40, len(tasks))))


if __name__ == "__main__":
    main()
