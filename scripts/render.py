"""Render the neofetch-style profile card (dark + light SVG).

Pulls live numbers from the GitHub GraphQL API and rewrites
dark_mode.svg / light_mode.svg. Runs nightly via .github/workflows/render.yml.

Private contributions are counted when the profile setting
"Include private contributions on my profile" is on, or when
GH_STATS_TOKEN belongs to the profile owner.
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

USER = "dolgoonnn"
CAREER_START = date(2021, 11, 1)  # first engineering job
ROOT = Path(__file__).resolve().parent.parent

LOGO = [
    r"       __      __                       ",
    r"  ____/ /___  / /___ _____  ____  ____  ",
    r" / __  / __ \/ / __ `/ __ \/ __ \/ __ \ ",
    r"/ /_/ / /_/ / / /_/ / /_/ / /_/ / / / / ",
    r"\__,_/\____/_/\__, /\____/\____/_/ /_/  ",
    r"             /____/                     ",
]


@dataclass(frozen=True)
class Stats:
    public_repos: int
    followers: int
    contributions_this_year: int
    contributions_all_time: int


@dataclass(frozen=True)
class Theme:
    name: str
    background: str
    border: str
    logo: str
    key: str
    value: str
    muted: str
    accent: str


DARK = Theme("dark", "#0d1117", "#30363d", "#79c0ff", "#ffa657", "#c9d1d9", "#6e7681", "#7ee787")
LIGHT = Theme("light", "#f6f8fa", "#d0d7de", "#0969da", "#953800", "#24292f", "#8c959f", "#1a7f37")


def graphql(query: str, variables: dict[str, object] | None = None) -> dict[str, object]:
    token = os.environ.get("GH_STATS_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("Set GH_STATS_TOKEN or GITHUB_TOKEN")
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if payload.get("errors"):
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    return payload["data"]


def fetch_stats() -> Stats:
    base = graphql(
        """query($login: String!) {
          user(login: $login) {
            followers { totalCount }
            repositories(ownerAffiliations: OWNER, privacy: PUBLIC) { totalCount }
            contributionsCollection { contributionYears }
          }
        }""",
        {"login": USER},
    )["user"]

    per_year: dict[int, int] = {}
    for year in base["contributionsCollection"]["contributionYears"]:
        collection = graphql(
            """query($login: String!, $from: DateTime!, $to: DateTime!) {
              user(login: $login) {
                contributionsCollection(from: $from, to: $to) {
                  contributionCalendar { totalContributions }
                }
              }
            }""",
            {"login": USER, "from": f"{year}-01-01T00:00:00Z", "to": f"{year}-12-31T23:59:59Z"},
        )["user"]["contributionsCollection"]
        per_year[year] = collection["contributionCalendar"]["totalContributions"]

    return Stats(
        public_repos=base["repositories"]["totalCount"],
        followers=base["followers"]["totalCount"],
        contributions_this_year=per_year.get(date.today().year, 0),
        contributions_all_time=sum(per_year.values()),
    )


def uptime(today: date) -> str:
    months = (today.year - CAREER_START.year) * 12 + today.month - CAREER_START.month
    if today.day < CAREER_START.day:
        months -= 1
    years, months = divmod(months, 12)
    return f"{years} years, {months} months"


def card_lines(stats: Stats, today: date) -> list[tuple[str, str] | str]:
    """Each entry is (key, value), a section header string, or "" for a blank line."""
    return [
        "# dolgoon@ulaanbaatar",
        "---",
        ("OS", "Mongolia, UTC+8"),
        ("Uptime", uptime(today)),
        ("Host", "Dreamon · CTO"),
        ("Kernel", "Multi-tenant commerce: B2C · B2B · marketplace"),
        ("Stack", "TypeScript · NestJS · Next.js · Prisma · Postgres"),
        ("AI", "Claude API · MCP servers · Claude Code"),
        ("Previously", "Bitcoin Ordinals · BRC-20 · EVM · UTXO"),
        "",
        "- Building",
        ("dream.mn", "Dreamon ecosystem · 15+ services, 7+ tenants"),
        ("capitalmarkets", "Mongolia's capital markets, for global investors"),
        ("Commerce MCP", "run catalog + finance ops from Claude"),
        "",
        "- GitHub (incl. private)",
        ("Contributions", f"{stats.contributions_this_year:,} this year · {stats.contributions_all_time:,} all-time"),
        ("Repos", f"{stats.public_repos} public · Followers {stats.followers}"),
        "",
        "$ ",
    ]


KEY_WIDTH = 16
CARD_WIDTH = 66
CHAR_W = 9.6  # 16px monospace advance
LINE_H = 22
LOGO_FONT = 18
LOGO_CHAR_W = CHAR_W * LOGO_FONT / 16
LOGO_LINE_H = 24
PAD = 24


def render_svg(theme: Theme, stats: Stats, today: date) -> str:
    lines = card_lines(stats, today)
    logo_cols = max(len(row) for row in LOGO)
    card_x = PAD + logo_cols * LOGO_CHAR_W + 3 * CHAR_W
    width = int(card_x + CARD_WIDTH * CHAR_W + PAD)
    height = PAD * 2 + LINE_H * len(lines)

    out: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="SFMono-Regular,Menlo,Consolas,\'DejaVu Sans Mono\',\'Liberation Mono\',monospace" font-size="16px">',
        "<style>@keyframes in{from{opacity:0}to{opacity:1}}"
        ".l{animation:in .35s ease-out backwards}"
        "@keyframes blink{50%{opacity:0}}.c{animation:blink 1.1s step-end infinite}</style>",
        f'<rect width="{width}" height="{height}" rx="12" fill="{theme.background}" stroke="{theme.border}"/>',
    ]

    logo_top = PAD + (height - 2 * PAD - LOGO_LINE_H * len(LOGO)) / 2 + 14
    for i, row in enumerate(LOGO):
        out.append(
            f'<text x="{PAD}" y="{logo_top + i * LOGO_LINE_H:.0f}" fill="{theme.logo}" font-size="{LOGO_FONT}px" font-weight="bold" '
            f'xml:space="preserve" class="l" style="animation-delay:{i * 0.08:.2f}s">{escape(row)}</text>'
        )

    for i, line in enumerate(lines):
        y = PAD + 16 + i * LINE_H
        delay = f'style="animation-delay:{0.5 + i * 0.06:.2f}s"'
        if line == "":
            continue
        if line == "$ ":
            body = (
                f'<tspan fill="{theme.accent}">dolgoon@ulaanbaatar</tspan>'
                f'<tspan fill="{theme.value}"> ~ $ </tspan>'
                f'<tspan fill="{theme.value}" class="c">█</tspan>'
            )
        elif line == "---":
            body = f'<tspan fill="{theme.muted}">{"─" * CARD_WIDTH}</tspan>'
        elif isinstance(line, str) and line.startswith("# "):
            user, host = line[2:].split("@")
            body = (
                f'<tspan fill="{theme.key}" font-weight="bold">{escape(user)}</tspan>'
                f'<tspan fill="{theme.value}">@</tspan>'
                f'<tspan fill="{theme.key}" font-weight="bold">{escape(host)}</tspan>'
            )
        elif isinstance(line, str) and line.startswith("- "):
            title = f"─ {line[2:]} "
            body = f'<tspan fill="{theme.accent}">{escape(title)}{"─" * (CARD_WIDTH - len(title))}</tspan>'
        else:
            key, value = line
            dots = " " + "." * (KEY_WIDTH - len(key) - 1) + " "
            body = (
                f'<tspan fill="{theme.key}">{escape(key)}</tspan>'
                f'<tspan fill="{theme.muted}">{dots}</tspan>'
                f'<tspan fill="{theme.value}">{escape(value)}</tspan>'
            )
        out.append(f'<text x="{card_x:.0f}" y="{y}" xml:space="preserve" class="l" {delay}>{body}</text>')

    out.append("</svg>")
    return "\n".join(out) + "\n"


def main() -> None:
    stats = fetch_stats()
    today = date.today()
    for theme in (DARK, LIGHT):
        (ROOT / f"{theme.name}_mode.svg").write_text(render_svg(theme, stats, today), encoding="utf-8")
    print(f"Rendered with {stats}")


if __name__ == "__main__":
    main()
