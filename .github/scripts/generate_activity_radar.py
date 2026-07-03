#!/usr/bin/env python3
"""Generate the README activity radar SVG from GitHub contribution data.

Percentage split of the last year's contributions across Commits, Code
review, Issues, and Pull requests, fetched from the GitHub GraphQL API.
The activity-radar workflow runs this daily and commits the result so
the chart stays live without depending on any third-party render service.

Usage:
    GITHUB_TOKEN=<token> python .github/scripts/generate_activity_radar.py

Note: per-type totals only cover contributions the token can see. The
default Actions GITHUB_TOKEN sees public contributions only; to include
private/org work, set the ACTIVITY_RADAR_TOKEN repo secret to a classic
PAT with repo + read:org scopes.
"""

import json
import os
import sys
import urllib.request
from pathlib import Path

USERNAME = "krittapastrycode"
OUTPUT = Path(__file__).resolve().parents[2] / "assets" / "activity-radar.svg"

WIDTH, HEIGHT = 480, 390
CENTER_X, CENTER_Y = 240, 195
AXIS_RADIUS = 110
LABEL_GAP = 16

BACKGROUND = "#0d1117"
TEXT = "#ffffff"
MUTED = "#8b949e"
GREEN = "#58a6ff"
GREEN_FILL = "#58a6ff66"

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      totalCommitContributions
      totalPullRequestReviewContributions
      totalIssueContributions
      totalPullRequestContributions
    }
  }
}
"""


def fetch_contributions(token: str) -> dict:
    payload = json.dumps({"query": QUERY, "variables": {"login": USERNAME}}).encode()
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.load(response)
    if "errors" in body:
        raise RuntimeError(f"GraphQL errors: {body['errors']}")
    return body["data"]["user"]["contributionsCollection"]


def axis_points(values: list[float]) -> list[tuple[float, float]]:
    """Vertex per axis in order: top, right, bottom, left (scaled to max)."""
    peak = max(values) or 1.0
    radii = [AXIS_RADIUS * value / peak for value in values]
    return [
        (CENTER_X, CENTER_Y - radii[0]),
        (CENTER_X + radii[1], CENTER_Y),
        (CENTER_X, CENTER_Y + radii[2]),
        (CENTER_X - radii[3], CENTER_Y),
    ]


def label_block(x: float, y: float, percent: int, name: str, anchor: str) -> str:
    return (
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" class="pct">{percent}%</text>'
        f'<text x="{x}" y="{y + 17}" text-anchor="{anchor}" class="name">{name}</text>'
    )


def render(percents: list[int]) -> str:
    """percents in axis order: code review, issues, pull requests, commits."""
    vertices = axis_points([float(p) for p in percents])
    polygon = " ".join(f"{x:.1f},{y:.1f}" for x, y in vertices)
    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{GREEN}"/>' for x, y in vertices
    )
    top = CENTER_Y - AXIS_RADIUS
    bottom = CENTER_Y + AXIS_RADIUS
    left = CENTER_X - AXIS_RADIUS
    right = CENTER_X + AXIS_RADIUS

    labels = (
        label_block(CENTER_X, top - LABEL_GAP - 17, percents[0], "Code review", "middle")
        + label_block(right + LABEL_GAP, CENTER_Y - 4, percents[1], "Issues", "start")
        + label_block(CENTER_X, bottom + LABEL_GAP + 12, percents[2], "Pull requests", "middle")
        + label_block(left - LABEL_GAP, CENTER_Y - 4, percents[3], "Commits", "end")
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}"
     viewBox="0 0 {WIDTH} {HEIGHT}" role="img"
     aria-label="Contribution split: {percents[3]}% commits, {percents[2]}% pull requests,
 {percents[0]}% code review, {percents[1]}% issues">
  <style>
    text {{ font-family: -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif; }}
    .pct {{ font-size: 14px; font-weight: 600; fill: {TEXT}; }}
    .name {{ font-size: 13px; fill: {MUTED}; }}
  </style>
  <rect width="{WIDTH}" height="{HEIGHT}" rx="10" fill="{BACKGROUND}"/>
  <line x1="{CENTER_X}" y1="{top}" x2="{CENTER_X}" y2="{bottom}" stroke="{GREEN}" stroke-width="1.5"/>
  <line x1="{left}" y1="{CENTER_Y}" x2="{right}" y2="{CENTER_Y}" stroke="{GREEN}" stroke-width="1.5"/>
  <polygon points="{polygon}" fill="{GREEN_FILL}" stroke="{GREEN}" stroke-width="1.5"/>
  {dots}
  {labels}
</svg>
"""


def main() -> int:
    token = os.environ.get("ACTIVITY_RADAR_TOKEN") or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("error: set ACTIVITY_RADAR_TOKEN, GITHUB_TOKEN, or GH_TOKEN", file=sys.stderr)
        return 1

    totals = fetch_contributions(token)
    counts = {
        "Code review": totals["totalPullRequestReviewContributions"],
        "Issues": totals["totalIssueContributions"],
        "Pull requests": totals["totalPullRequestContributions"],
        "Commits": totals["totalCommitContributions"],
    }
    grand_total = sum(counts.values())
    if grand_total == 0:
        print("error: no contributions found in the last year", file=sys.stderr)
        return 1

    percents = [round(100 * value / grand_total) for value in counts.values()]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render(percents))
    summary = ", ".join(f"{name} {pct}%" for name, pct in zip(counts, percents))
    print(f"wrote {OUTPUT} ({summary})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
