"""Draw a reproducible, static comparison figure from the reviewed JSON summary."""

import argparse
import json
from pathlib import Path

from reportlab.graphics import renderSVG
from reportlab.graphics.shapes import Circle, Drawing, Line, Rect, String
from reportlab.lib.colors import HexColor, white

PROJECT = Path(__file__).resolve().parents[1]
DEFAULT = PROJECT / "ratings/archive/dialogue-benchmark-comparison"


def render_comparison(source, destination):
    """Show each agent's baseline and post-dialogue mean on the same 1-to-5 scale."""
    summary = json.loads(source.read_text())
    width, height = 1190, 690
    drawing = Drawing(width, height)
    ink = HexColor("#172b3a")
    muted = HexColor("#596b77")
    grid = HexColor("#dce3e7")
    baseline_color = HexColor("#738392")
    post_color = HexColor("#006e91")
    drawing.add(Rect(0, 0, width, height, fillColor=white, strokeColor=None))

    def text(x, y, value, size=12, color=ink, anchor="start", bold=False):
        drawing.add(
            String(
                x,
                y,
                value,
                fontName="Helvetica-Bold" if bold else "Helvetica",
                fontSize=size,
                fillColor=color,
                textAnchor=anchor,
            )
        )

    text(
        30,
        653,
        "Ratings after dialogue compared with individual benchmarks",
        23,
        bold=True,
    )
    text(
        30,
        626,
        f"{summary['complete_pairs']} complete dialogue trials per agent; 200 individual benchmark runs per agent",
        13,
        muted,
    )
    text(
        30,
        599,
        "Agreement scale: 1 strongly disagree  |  2 disagree  |  3 neutral  |  4 agree  |  5 strongly agree",
        12,
        muted,
    )
    first_y, gap, low_y = 533, 34, 130
    label_width = 345
    for i, label in enumerate(summary["statement_short_labels"]):
        y = first_y - i * gap
        text(30, y - 4, f"S{i + 1}  {label}", 12)
        drawing.add(
            Line(30, y - 17, width - 30, y - 17, strokeColor=grid, strokeWidth=0.5)
        )
    for panel, (agent, name) in enumerate(
        (("agent_a", "Skeptic"), ("agent_b", "Extrapolator"))
    ):
        left = label_width + panel * 405
        plot_width = 300
        text(left + plot_width / 2, 565, name, 17, anchor="middle", bold=True)
        text(left + plot_width + 40, 565, "Change", 11, muted, anchor="middle")
        for score in range(1, 6):
            x = left + (score - 1) * plot_width / 4
            drawing.add(
                Line(x, low_y, x, first_y + 13, strokeColor=grid, strokeWidth=0.7)
            )
            text(x, low_y - 19, str(score), 11, muted, anchor="middle")
        before = summary["baseline"][agent]["means"]
        after = summary["post_dialogue"][agent]["means"]
        for i, (base, post) in enumerate(zip(before, after)):
            y = first_y - i * gap
            bx = left + (base - 1) * plot_width / 4
            px = left + (post - 1) * plot_width / 4
            drawing.add(Line(bx, y, px, y, strokeColor=baseline_color, strokeWidth=2))
            drawing.add(
                Circle(
                    bx,
                    y,
                    4.5,
                    fillColor=white,
                    strokeColor=baseline_color,
                    strokeWidth=1.6,
                )
            )
            drawing.add(Circle(px, y, 4.2, fillColor=post_color, strokeColor=None))
            text(
                left + plot_width + 40,
                y - 4,
                f"{post - base:+.2f}",
                11,
                anchor="middle",
            )
    drawing.add(
        Circle(
            35, 79, 4.5, fillColor=white, strokeColor=baseline_color, strokeWidth=1.6
        )
    )
    text(47, 75, "Individual benchmark mean", 12)
    drawing.add(Circle(272, 79, 4.2, fillColor=post_color, strokeColor=None))
    text(284, 75, "Post-dialogue mean", 12)
    text(
        30,
        47,
        "Positive change means more agreement with that statement. Mean scores assume equally spaced Likert categories.",
        11,
        muted,
    )
    text(
        30,
        27,
        "Comparison includes seeded memory and prompt changes; it does not isolate a causal effect of dialogue. Complete trials only.",
        11,
        muted,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    renderSVG.drawToFile(drawing, str(destination))
    print(destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT / "comparison.json")
    parser.add_argument("--output", type=Path, default=DEFAULT / "comparison.svg")
    args = parser.parse_args()
    render_comparison(args.source, args.output)
