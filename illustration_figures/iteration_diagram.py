"""
iteration_diagram.py
--------------------
Draw one round of the model as a horizontal flow: the poll, the runoff guess, the tolerable candidates,
the trigger, the choice, and the count that feeds the next poll.

Unlike the other scripts here, its output is committed, because docs/model.md shows it. It is plain SVG
written by hand rather than with matplotlib, in a light and a dark version that GitHub picks between.

Outputs
-------
    docs/figures/iteration.svg
    docs/figures/iteration-dark.svg

Usage
-----
    python illustration_figures/iteration_diagram.py
"""

from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "docs" / "figures"

# The interactive page's palette (docs/index.html), so the diagram matches it.
THEMES = {
    "light": dict(card="#f5f5f2", edge="#cfcfca", ink="#1a1a1a", muted="#5f6368", arrow="#8a8f94",
                  accent="#2f5d8a", wash="#eaf1f8", ok="#2c6a4f", ok_wash="#eef5f1", on_accent="#ffffff"),
    "dark": dict(card="#1c1f22", edge="#41464b", ink="#e8e6e3", muted="#a3a6aa", arrow="#7d8186",
                 accent="#82b4e2", wash="#1b2733", ok="#7cc4a1", ok_wash="#17261f", on_accent="#131517"),
}

W, H = 1200, 290
MID = 110            # vertical centre of the main row
BOX_H = 104
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"


def box(x, y, w, h, n, title, body, maths, fill="card", edge="edge", badge="accent"):
    cx = x + w / 2
    return f"""
  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" class="f-{fill} s-{edge}" stroke-width="1.5"/>
  <circle cx="{x + 18}" cy="{y + 18}" r="11" class="f-{badge}"/>
  <text x="{x + 18}" y="{y + 22.5}" class="badge">{n}</text>
  <text x="{cx}" y="{y + 44}" class="title">{title}</text>
  <text x="{cx}" y="{y + 66}" class="body">{body}</text>
  <text x="{cx}" y="{y + 90}" class="maths">{maths}</text>"""


def arrow(x1, y1, x2, y2, cls="s-arrow"):
    return f'\n  <path d="M{x1},{y1} L{x2},{y2}" class="{cls}" stroke-width="1.8" fill="none" marker-end="url(#head)"/>'


def svg(theme):
    c = THEMES[theme]
    top = MID - BOX_H / 2
    parts = [f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img"
     aria-labelledby="t d">
  <title id="t">One round of the model</title>
  <desc id="d">Every voter reads the poll, guesses which two candidates reach the runoff, and lists the candidates
    they tolerate. If one of those is in the runoff they stay with their favourite; otherwise they switch when the gain
    beats the cost. The votes are counted and feed the next round.</desc>
  <style>
    text {{ font-family: {FONT}; text-anchor: middle; }}
    .title {{ font-size: 17px; font-weight: 600; fill: {c['ink']}; }}
    .body {{ font-size: 14px; fill: {c['muted']}; }}
    .maths {{ font-family: {MONO}; font-size: 13px; fill: {c['accent']}; }}
    .badge {{ font-size: 13px; font-weight: 700; fill: {c['on_accent']}; }}
    .label {{ font-size: 14px; font-weight: 600; }}
    .loop {{ font-size: 14px; fill: {c['muted']}; }}
    .f-card {{ fill: {c['card']}; }} .f-wash {{ fill: {c['wash']}; }} .f-ok-wash {{ fill: {c['ok_wash']}; }}
    .f-accent {{ fill: {c['accent']}; }} .f-ok {{ fill: {c['ok']}; }}
    .s-edge {{ stroke: {c['edge']}; }} .s-accent {{ stroke: {c['accent']}; }} .s-ok {{ stroke: {c['ok']}; }}
    .s-arrow {{ stroke: {c['arrow']}; }}
    .t-ok {{ fill: {c['ok']}; }} .t-accent {{ fill: {c['accent']}; }}
  </style>
  <defs>
    <marker id="head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
      <path d="M0,0 L10,5 L0,10 z" fill="{c['arrow']}"/>
    </marker>
  </defs>"""]

    # Steps 1 to 3, left to right.
    parts.append(box(0, top, 150, BOX_H, 1, "The poll", "same for everyone", "sᵗ"))
    parts.append(arrow(151, MID, 180, MID))
    parts.append(box(184, top, 186, BOX_H, 2, "Guess the runoff", "top two in their beliefs",
                     "α·π + (1−α)·sᵗ"))
    parts.append(arrow(371, MID, 400, MID))
    parts.append(box(404, top, 186, BOX_H, 3, "Who they tolerate", "candidates close enough",
                     "|x − xⱼ| ≤ τ"))
    parts.append(arrow(591, MID, 618, MID))

    # Step 4, the trigger.
    dx, dh = 700, 80
    parts.append(f"""
  <path d="M{dx},{MID - dh} L{dx + dh},{MID} L{dx},{MID + dh} L{dx - dh},{MID} z" class="f-wash s-accent"
        stroke-width="1.5"/>
  <circle cx="{dx}" cy="{MID - dh + 24}" r="11" class="f-accent"/>
  <text x="{dx}" y="{MID - dh + 28.5}" class="badge">4</text>
  <text x="{dx}" y="{MID - 6}" class="body" style="fill:{c['ink']}">A tolerable one</text>
  <text x="{dx}" y="{MID + 13}" class="body" style="fill:{c['ink']}">in the runoff?</text>""")

    # Step 5, the two outcomes.
    fx, fw, fh = 830, 196, 96
    ytop, ybot = 6, MID + 14
    parts.append(f'\n  <path d="M{dx + 40},{MID - 40} C{dx + 70},{ytop + fh / 2} {fx - 30},{ytop + fh / 2} '
                 f'{fx - 3},{ytop + fh / 2}" class="s-arrow" stroke-width="1.8" fill="none" marker-end="url(#head)"/>')
    parts.append(f'\n  <path d="M{dx + 40},{MID + 40} C{dx + 70},{ybot + fh / 2} {fx - 30},{ybot + fh / 2} '
                 f'{fx - 3},{ybot + fh / 2}" class="s-arrow" stroke-width="1.8" fill="none" marker-end="url(#head)"/>')
    parts.append(f'\n  <text x="{dx + 72}" y="{ytop + 30}" class="label t-ok">yes</text>')
    parts.append(f'\n  <text x="{dx + 72}" y="{ybot + fh - 18}" class="label t-accent">no</text>')
    for y, title, body, maths, cls, wash in [(ytop, "Stay", "with their favourite", "j*", "ok", "ok-wash"),
                                      (ybot, "Maybe switch", "if the gain beats the cost", "cost weighted by μ",
                                              "accent", "wash")]:
        parts.append(f"""
  <rect x="{fx}" y="{y}" width="{fw}" height="{fh}" rx="12" class="f-{wash} s-{cls}" stroke-width="1.5"/>
  <text x="{fx + fw / 2}" y="{y + 36}" class="title">{title}</text>
  <text x="{fx + fw / 2}" y="{y + 60}" class="body">{body}</text>
  <text x="{fx + fw / 2}" y="{y + 84}" class="maths">{maths}</text>""")

    # Step 6, the count, which feeds the next round.
    kx, kw = 1054, 146
    parts.append(f'\n  <path d="M{fx + fw + 1},{ytop + fh / 2} C{kx - 14},{ytop + fh / 2} {kx - 24},{MID} '
                 f'{kx - 3},{MID}" class="s-arrow" stroke-width="1.8" fill="none" marker-end="url(#head)"/>')
    parts.append(f'\n  <path d="M{fx + fw + 1},{ybot + fh / 2} C{kx - 14},{ybot + fh / 2} {kx - 24},{MID} '
                 f'{kx - 3},{MID}" class="s-arrow" stroke-width="1.8" fill="none"/>')
    parts.append(box(kx, top, kw, BOX_H, 5, "Count votes", "new vote shares", "ENP, CENP"))

    ly = 262
    parts.append(f'\n  <path d="M{kx + kw / 2},{top + BOX_H + 1} L{kx + kw / 2},{ly} L75,{ly} L75,{top + BOX_H + 4}" '
                 f'class="s-accent" stroke-width="1.8" stroke-dasharray="6 5" fill="none" marker-end="url(#head)"/>')
    parts.append(f'\n  <text x="540" y="{ly - 9}" class="loop">next round: the votes shape the next poll, '
                 f'or the next real poll is read</text>')
    parts.append("\n</svg>\n")
    return "".join(parts)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for theme, name in [("light", "iteration.svg"), ("dark", "iteration-dark.svg")]:
        (OUT / name).write_text(svg(theme), encoding="utf-8")
        print(f"wrote {OUT / name}")


if __name__ == "__main__":
    main()
