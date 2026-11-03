"""Dependency-free SVG plots for locked motor fault simulation results.

Figures are descriptive only: error bars are Wilson 95% intervals for
episode-level proportions; paired conditions are not independent devices.
"""
import argparse
import json
import math
from pathlib import Path
from xml.sax.saxutils import escape

METHODS = ("tracking", "no_load", "load_augmented")
COLORS = {"tracking": "#64748b", "no_load": "#2563eb", "load_augmented": "#0f766e"}
NAMES = {"tracking": "Tracking error",
         "no_load": "Current-only, no load",
         "load_augmented": "Current-only, + load"}
LABELS = {
    "healthy": "Healthy — nominal variability",
    "healthy_shift": "Healthy — shifted parameters",
    "bias": "Speed-sensor offset",
    "drift": "Speed-sensor drift",
    "stuck": "Stuck speed sensor",
    "bias_shift": "Offset + parameter shift",
}
CHARTS = {
    "false_alarms.svg": (
        ("healthy", "healthy_shift"),
        "Healthy-episode false alarms",
        "Lower is better. Parameter-shift stress testing lies outside calibration distribution.",
        "false_alarm_fraction",
    ),
    "detections.svg": (
        ("bias", "drift", "stuck", "bias_shift"),
        "Valid speed-sensor fault detections",
        "Higher is better. A pre-fault alarm disqualifies an episode as a valid detection.",
        "valid_detection_fraction",
    ),
}


def validate_summary(payload):
    if payload.get("protocol") != "PROTOCOL.md v1":
        raise ValueError("Expected locked protocol v1 results")
    for filename, (conditions, _, _, metric) in CHARTS.items():
        for condition in conditions:
            for method in METHODS:
                d = payload["results"][condition][method]
                n, count, rate, ci = d["n"], d["count"], d["rate"], d["wilson95"]
                if (d.get("metric") != metric or not isinstance(n, int)
                        or not isinstance(count, int) or n <= 0 or not 0 <= count <= n
                        or len(ci) != 2 or not all(math.isfinite(v) for v in (rate, *ci))
                        or not (-1e-12 <= ci[0] <= rate + 1e-12 and
                                rate - 1e-12 <= ci[1] <= 1 + 1e-12)
                        or not math.isclose(count / n, rate, abs_tol=1e-12)):
                    raise ValueError(f"Invalid data: {filename}, {condition}, {method}")


def render_chart(payload, filename):
    validate_summary(payload)
    conditions, title, subtitle, _ = CHARTS[filename]
    w, h = 1180, 135 + len(conditions) * 155
    x0, span, ystart = 330, 635, 115
    s = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}">',
        f"<title>{escape(title)}</title>",
        "<desc>Sixty synthetic evaluation episodes per condition, paired by seed. "
        "Whiskers show Wilson 95% intervals. Not a hardware result.</desc>",
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
        f'<text x="35" y="42" font-family="Arial,sans-serif" font-size="24" font-weight="700" fill="#0f172a">{escape(title)}</text>',
        f'<text x="35" y="70" font-family="Arial,sans-serif" font-size="15" fill="#475569">{escape(subtitle)}</text>',
    ]
    for tick in range(0, 101, 25):
        x = x0 + span * tick / 100
        s.extend((
            f'<line x1="{x}" x2="{x}" y1="90" y2="{h - 58}" stroke="#e2e8f0" stroke-width="1"/>',
            f'<text x="{x}" y="{h - 37}" text-anchor="middle" font-family="Arial,sans-serif" font-size="12" fill="#475569">{tick}%</text>',
        ))
    for index, condition in enumerate(conditions):
        y = ystart + index * 155
        if index % 2 == 0:
            s.append(f'<rect x="20" y="{y - 21}" width="1120" height="146" rx="8" fill="#f8fafc"/>')
        s.append(f'<text x="35" y="{y}" font-family="Arial,sans-serif" font-size="17" font-weight="700" fill="#0f172a">{escape(LABELS[condition])}</text>')
        for j, method in enumerate(METHODS):
            d = payload["results"][condition][method]
            yt = y + 15 + j * 33
            rate = 100 * d["rate"]
            lo, hi = (100 * v for v in d["wilson95"])
            bx = x0 + span * rate / 100
            xlo, xhi = x0 + span * lo / 100, x0 + span * hi / 100
            s.extend((
                f'<text x="35" y="{yt + 13}" font-family="Arial,sans-serif" font-size="14" fill="#334155">{escape(NAMES[method])}</text>',
                f'<rect x="{x0}" y="{yt}" height="19" width="{span * rate / 100}" rx="3" fill="{COLORS[method]}"/>',
                f'<line x1="{xlo}" x2="{xhi}" y1="{yt + 9.5}" y2="{yt + 9.5}" stroke="#111827" stroke-width="1.5"/>',
                f'<line x1="{xlo}" x2="{xlo}" y1="{yt + 4}" y2="{yt + 15}" stroke="#111827" stroke-width="1.5"/>',
                f'<line x1="{xhi}" x2="{xhi}" y1="{yt + 4}" y2="{yt + 15}" stroke="#111827" stroke-width="1.5"/>',
                f'<circle cx="{bx}" cy="{yt + 9.5}" r="3" fill="#111827"/>',
                f'<text x="985" y="{yt + 13}" font-family="Arial,sans-serif" font-size="14" fill="#0f172a">{d["count"]}/{d["n"]} ({rate:.1f}%)</text>',
            ))
    s.append(f'<text x="35" y="{h - 10}" font-family="Arial,sans-serif" font-size="12" fill="#64748b">Synthetic model only · Wilson 95% intervals · locked protocol v1 · 29 Oct 2026</text>')
    s.append("</svg>")
    return "\n".join(s) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, default=Path("results/run_v1/summary.json"))
    parser.add_argument("--out", type=Path, default=Path("figures"))
    args = parser.parse_args()
    payload = json.loads(args.summary.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    for filename in CHARTS:
        (args.out / filename).write_text(render_chart(payload, filename), encoding="utf-8")
        print(args.out / filename)


if __name__ == "__main__":
    main()
