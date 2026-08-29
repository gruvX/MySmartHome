#!/usr/bin/env python3
"""Render architecture-only Plan 3 JSON as a self-contained interactive SVG.

The export deliberately excludes plan ids, comments, electrical routes, addresses,
and item metadata.  It is suitable for the authenticated tablet panel iframe.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def points(value: list[dict[str, float]]) -> str:
    return " ".join(f"{float(p['x']):.2f},{float(p['y']):.2f}" for p in value)


def centroid(value: list[dict[str, float]]) -> tuple[float, float]:
    # A label centroid only; the SVG geometry remains the exact source polygon.
    return (
        sum(float(p["x"]) for p in value) / len(value),
        sum(float(p["y"]) for p in value) / len(value),
    )


def render(source: Path, target: Path) -> None:
    plan = json.loads(source.read_text(encoding="utf-8"))["plan"]
    drawing = plan["drawing"]
    pad = 42
    x = float(drawing["x_min"]) - pad
    y = float(drawing["y_min"]) - pad
    width = float(drawing["width"]) + pad * 2
    height = float(drawing["height"]) + pad * 2

    rooms = []
    labels = []
    palette = ["#172b34", "#1b3038", "#20343b", "#193039", "#24363b", "#1d3239", "#22383d"]
    for index, room in enumerate(plan.get("rooms2", {}).values(), start=1):
        polygon = room.get("polygon") or []
        if len(polygon) < 3:
            continue
        rooms.append(
            f'<polygon class="room" points="{points(polygon)}" fill="{palette[(index-1) % len(palette)]}"/>'
        )
        cx, cy = centroid(polygon)
        area = room.get("area")
        labels.append(
            f'<g class="room-label" transform="translate({cx:.2f} {cy:.2f})">'
            f'<text class="room-name" text-anchor="middle">Помещение {index}</text>'
            f'<text class="room-area" y="22" text-anchor="middle">{html.escape(str(area))} м²</text></g>'
        )

    walls = []
    for wall in plan.get("walls", {}).values():
        p1, p2 = wall.get("p1") or {}, wall.get("p2") or {}
        if not all(k in p1 and k in p2 for k in ("x", "y")):
            continue
        depth = max(8.0, float(wall.get("depth") or 18))
        walls.append(
            f'<line class="wall" x1="{float(p1["x"]):.2f}" y1="{float(p1["y"]):.2f}" '
            f'x2="{float(p2["x"]):.2f}" y2="{float(p2["y"]):.2f}" stroke-width="{depth:.2f}"/>'
        )

    body = f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>План первого этажа</title><style>
:root{{--bg:#071016;--panel:#0d1a20;--ink:#f3f7f8;--muted:#9babb2;--cyan:#50d5ff;--line:#30434b}}
*{{box-sizing:border-box}}html,body{{height:100%;margin:0;background:var(--bg);color:var(--ink);font-family:system-ui,sans-serif;overflow:hidden}}
.app{{height:100%;display:grid;grid-template-rows:auto 1fr}}header{{display:flex;align-items:center;gap:12px;padding:12px 16px;background:var(--panel);border-bottom:1px solid var(--line)}}
h1{{font-size:18px;margin:0}}.note{{font-size:11px;color:var(--muted)}}.spacer{{flex:1}}button{{height:34px;padding:0 12px;border:1px solid var(--line);border-radius:8px;background:#14252c;color:var(--ink);cursor:pointer}}
.stage{{position:relative;min-height:0;overflow:hidden;touch-action:none;background:radial-gradient(circle at 50% 42%,#10242c,#071016 72%)}}svg{{width:100%;height:100%;display:block}}#world{{transform-origin:0 0}}.room{{stroke:#3b535d;stroke-width:2}}.wall{{stroke:#d6e1e4;stroke-linecap:square}}.room-label{{pointer-events:none}}.room-name{{fill:var(--ink);font-size:19px;font-weight:700}}.room-area{{fill:var(--cyan);font-size:15px;font-weight:700}}
.legend{{position:absolute;left:14px;bottom:14px;max-width:360px;padding:9px 11px;border-radius:9px;background:rgba(7,16,22,.88);color:var(--muted);font-size:11px;border:1px solid var(--line)}}
@media(max-width:700px){{header{{padding:9px 10px}}.note{{display:none}}h1{{font-size:15px}}}}
</style></head><body><div class="app"><header><h1>План первого этажа</h1><span class="note">точная геометрия из Plan 3 · без электрических данных</span><span class="spacer"></span><button id="reset">Вписать</button></header>
<main class="stage" id="stage"><svg id="plan" viewBox="{x:.2f} {y:.2f} {width:.2f} {height:.2f}" aria-label="Архитектурный план первого этажа"><g id="world">{''.join(rooms)}{''.join(walls)}{''.join(labels)}</g></svg><div class="legend">Колесо — масштаб · перетаскивание — перемещение. Названия помещений пока нейтральные: назначение комнат нужно сверить с владельцем.</div></main></div>
<script>
const svg=document.querySelector('#plan'),world=document.querySelector('#world'),stage=document.querySelector('#stage');let scale=1,tx=0,ty=0,drag=false,px=0,py=0;
function paint(){{world.setAttribute('transform',`translate(${{tx}} ${{ty}}) scale(${{scale}})`)}}function reset(){{scale=1;tx=0;ty=0;paint()}}
stage.addEventListener('wheel',e=>{{e.preventDefault();const k=e.deltaY<0?1.12:.89;scale=Math.max(.55,Math.min(4,scale*k));paint()}},{{passive:false}});
stage.addEventListener('pointerdown',e=>{{drag=true;px=e.clientX;py=e.clientY;stage.setPointerCapture(e.pointerId)}});stage.addEventListener('pointermove',e=>{{if(!drag)return;tx+=(e.clientX-px)/scale;ty+=(e.clientY-py)/scale;px=e.clientX;py=e.clientY;paint()}});stage.addEventListener('pointerup',()=>drag=false);document.querySelector('#reset').onclick=reset;
</script></body></html>"""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    render(args.source, args.target)


if __name__ == "__main__":
    main()
