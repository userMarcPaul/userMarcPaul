"""
Generates matrix-themed GitHub stats SVGs for a profile README.

Outputs:
  assets/stats.svg     terminal-style stats + top languages
  assets/activity.svg  contribution line graph (last 31 days)

Env vars:
  GH_TOKEN  GitHub token (the workflow passes this in)
  GH_USER   GitHub username
Run with --demo to render sample data without calling the API.
"""
import json, os, sys, random, urllib.request
from datetime import date
from xml.sax.saxutils import escape

USER = os.environ.get("GH_USER", "userMarcPaul")
TOKEN = os.environ.get("GH_TOKEN", "")
OUT = "assets"

# Matrix palette
BG = "#000000"
PANEL = "#020a04"
GREEN = "#00ff41"
MID = "#00b32d"
DIM = "#0a5c1f"
FAINT = "#063d14"
FONT = "'Courier New', Consolas, 'Liberation Mono', monospace"
LANG_SHADES = ["#00ff41", "#00cc34", "#009926", "#00661a", "#2bff6a", "#7dffa2"]

QUERY = """
query($login: String!) {
  user(login: $login) {
    login
    followers { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100,
                 orderBy: {field: STARGAZERS, direction: DESC}) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def fetch():
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json",
                 "User-Agent": "readme-stats"},
    )
    with urllib.request.urlopen(req) as r:
        payload = json.load(r)
    if "errors" in payload:
        sys.exit(f"GitHub API error: {payload['errors']}")
    u = payload["data"]["user"]
    cc = u["contributionsCollection"]
    days = [d for w in cc["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    langs = {}
    for repo in u["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            langs[e["node"]["name"]] = langs.get(e["node"]["name"], 0) + e["size"]
    return {
        "login": u["login"],
        "stars": sum(r["stargazerCount"] for r in u["repositories"]["nodes"]),
        "repos": u["repositories"]["totalCount"],
        "followers": u["followers"]["totalCount"],
        "commits": cc["totalCommitContributions"],
        "prs": cc["totalPullRequestContributions"],
        "issues": cc["totalIssueContributions"],
        "contributions": cc["contributionCalendar"]["totalContributions"],
        "days": days,
        "langs": langs,
    }


def demo():
    random.seed(7)
    today = date.today().toordinal()
    days = [{"date": date.fromordinal(today - i).isoformat(),
             "contributionCount": max(0, int(random.gauss(4, 4)))} for i in range(364, -1, -1)]
    for d in days[-6:]:
        d["contributionCount"] = d["contributionCount"] or 2
    return {"login": USER, "stars": 42, "repos": 27, "followers": 18, "commits": 512,
            "prs": 34, "issues": 12, "contributions": sum(d["contributionCount"] for d in days),
            "days": days,
            "langs": {"JavaScript": 52000, "TypeScript": 31000, "Python": 18000,
                      "Java": 12000, "Dart": 9000, "CSS": 6000, "HTML": 4000}}


def streak(days):
    counts = [d["contributionCount"] for d in days]
    # Today not counting yet shouldn't break the streak
    if counts and counts[-1] == 0:
        counts = counts[:-1]
    n = 0
    for c in reversed(counts):
        if c == 0:
            break
        n += 1
    return n


def rain(width, height, cols, seed):
    """Faint falling glyph columns behind the content."""
    rnd = random.Random(seed)
    glyphs = "ｱｲｳｴｵｶｷｸｹｺ01ﾊﾐﾋｰｳｼﾅﾓﾆｻﾜﾂｵﾘ"
    out = []
    for i in range(cols):
        x = int((i + 0.5) * width / cols)
        chars = "".join(f'<tspan x="{x}" dy="14">{rnd.choice(glyphs)}</tspan>' for _ in range(rnd.randint(6, 12)))
        dur = rnd.uniform(6, 12)
        delay = -rnd.uniform(0, dur)
        out.append(f'<text class="rain" style="animation-duration:{dur:.1f}s;animation-delay:{delay:.1f}s" y="-200">{chars}</text>')
    return "\n    ".join(out)


def stats_svg(d):
    W = 495
    rows = [
        ("stars", "Total stars", d["stars"]),
        ("commits", "Commits (past year)", d["commits"]),
        ("prs", "Pull requests (past year)", d["prs"]),
        ("issues", "Issues (past year)", d["issues"]),
        ("repos", "Public repos", d["repos"]),
        ("followers", "Followers", d["followers"]),
        ("contrib", "Contributions (past year)", d["contributions"]),
        ("streak", "Current streak", f'{streak(d["days"])} days'),
    ]
    top = sorted(d["langs"].items(), key=lambda kv: -kv[1])[:6]
    total = sum(v for _, v in top) or 1

    y0 = 78
    line_h = 22
    lines = []
    for i, (_, label, val) in enumerate(rows):
        y = y0 + i * line_h
        delay = 0.4 + i * 0.12
        dots = "." * max(2, 30 - len(label))
        lines.append(
            f'<g class="ln" style="animation-delay:{delay:.2f}s">'
            f'<text x="24" y="{y}" class="key">{escape(label)} <tspan class="dots">{dots}</tspan></text>'
            f'<text x="{W - 24}" y="{y}" class="val" text-anchor="end">{escape(str(val))}</text></g>'
        )

    ly = y0 + len(rows) * line_h + 14
    lang_delay = 0.4 + len(rows) * 0.12 + 0.2
    bar_w = W - 48
    bar = []
    x = 24.0
    for i, (name, size) in enumerate(top):
        w = bar_w * size / total
        bar.append(f'<rect x="{x:.2f}" y="{ly + 18}" width="{max(w - 1.5, 0.5):.2f}" height="8" fill="{LANG_SHADES[i]}"/>')
        x += w
    legend = []
    for i, (name, size) in enumerate(top):
        col, row = i % 3, i // 3
        lx = 24 + col * 152
        lyy = ly + 46 + row * 20
        legend.append(
            f'<rect x="{lx}" y="{lyy - 8}" width="8" height="8" fill="{LANG_SHADES[i]}"/>'
            f'<text x="{lx + 14}" y="{lyy}" class="leg">{escape(name)} <tspan class="pct">{size / total * 100:.1f}%</tspan></text>'
        )
    H = ly + 46 + ((len(top) + 2) // 3) * 20 + 10

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="GitHub stats for {escape(d["login"])}">
  <title>GitHub stats for {escape(d["login"])}</title>
  <style>
    text {{ font-family: {FONT}; }}
    .rain {{ fill: {FAINT}; opacity: 0.55; font-size: 13px; animation: fall linear infinite; }}
    @keyframes fall {{ from {{ transform: translateY(0); }} to {{ transform: translateY({H + 400}px); }} }}
    .prompt {{ fill: {MID}; font-size: 13px; }}
    .cmd {{ fill: {GREEN}; font-size: 13px; }}
    .key {{ fill: {MID}; font-size: 13px; }}
    .dots {{ fill: {DIM}; }}
    .val {{ fill: {GREEN}; font-size: 13px; font-weight: bold; }}
    .head {{ fill: {MID}; font-size: 13px; }}
    .leg {{ fill: {MID}; font-size: 12px; }}
    .pct {{ fill: {DIM}; }}
    .bar {{ fill: {FAINT}; }}
    .ln, .langs {{ opacity: 0; animation: show 0.01s forwards; }}
    @keyframes show {{ to {{ opacity: 1; }} }}
    .cursor {{ fill: {GREEN}; animation: blink 1s steps(1) infinite; }}
    @keyframes blink {{ 50% {{ opacity: 0; }} }}
    @media (prefers-reduced-motion: reduce) {{
      .rain {{ animation: none; display: none; }}
      .ln, .langs {{ animation: none; opacity: 1; }}
      .cursor {{ animation: none; }}
    }}
  </style>
  <defs><clipPath id="c"><rect width="{W}" height="{H}" rx="6"/></clipPath></defs>
  <g clip-path="url(#c)">
    <rect width="{W}" height="{H}" fill="{BG}"/>
    {rain(W, H, 18, 1)}
    <rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="6" fill="none" stroke="{DIM}"/>
    <rect x="1" y="1" width="{W - 2}" height="28" fill="{PANEL}"/>
    <line x1="0" y1="29" x2="{W}" y2="29" stroke="{DIM}"/>
    <circle cx="18" cy="15" r="4.5" fill="none" stroke="{MID}"/>
    <circle cx="34" cy="15" r="4.5" fill="none" stroke="{MID}"/>
    <circle cx="50" cy="15" r="4.5" fill="{MID}"/>
    <text x="{W / 2}" y="19" class="prompt" text-anchor="middle">{escape(d["login"])}@github: ~</text>
    <text x="24" y="54"><tspan class="prompt">$ </tspan><tspan class="cmd">./stats --user {escape(d["login"])}</tspan></text>
    {"".join(lines)}
    <g class="langs" style="animation-delay:{lang_delay:.2f}s">
      <text x="24" y="{ly + 8}" class="head">Top languages</text>
      <rect x="24" y="{ly + 18}" width="{bar_w}" height="8" class="bar"/>
      {"".join(bar)}
      {"".join(legend)}
      <rect x="{W - 32}" y="{ly - 2}" width="8" height="14" class="cursor"/>
    </g>
  </g>
</svg>'''


def activity_svg(d):
    days = d["days"][-31:]
    W, H = 850, 300
    L, R, T, B = 56, 24, 64, 46
    pw, ph = W - L - R, H - T - B
    counts = [x["contributionCount"] for x in days]
    mx = max(max(counts), 4)
    # Round axis max up to a tidy number
    step = max(1, -(-mx // 4))
    ymax = step * 4

    def px(i): return L + pw * i / (len(days) - 1)
    def py(v): return T + ph - ph * v / ymax

    pts = [(px(i), py(c)) for i, c in enumerate(counts)]
    path = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = path + f" L{pts[-1][0]:.1f},{T + ph} L{pts[0][0]:.1f},{T + ph} Z"

    grid = []
    for k in range(5):
        v = step * k
        y = py(v)
        grid.append(f'<line x1="{L}" y1="{y:.1f}" x2="{W - R}" y2="{y:.1f}" class="grid"/>'
                    f'<text x="{L - 10}" y="{y + 4:.1f}" class="axis" text-anchor="end">{v}</text>')
    xlabels = []
    for i in range(0, len(days), 5):
        dt = date.fromisoformat(days[i]["date"])
        xlabels.append(f'<text x="{px(i):.1f}" y="{H - B + 22}" class="axis" text-anchor="middle">{dt.strftime("%b %d")}</text>')
    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" class="pt"><title>{days[i]["date"]}: {counts[i]}</title></circle>'
        for i, (x, y) in enumerate(pts))

    total = sum(counts)
    best = max(counts)
    length = sum(((pts[i + 1][0] - pts[i][0]) ** 2 + (pts[i + 1][1] - pts[i][1]) ** 2) ** 0.5 for i in range(len(pts) - 1))

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Contribution graph for {escape(d["login"])}">
  <title>Contributions in the last 31 days for {escape(d["login"])}</title>
  <style>
    text {{ font-family: {FONT}; }}
    .rain {{ fill: {FAINT}; opacity: 0.55; font-size: 13px; animation: fall linear infinite; }}
    @keyframes fall {{ from {{ transform: translateY(0); }} to {{ transform: translateY({H + 400}px); }} }}
    .title {{ fill: {GREEN}; font-size: 15px; font-weight: bold; }}
    .sub {{ fill: {MID}; font-size: 12px; }}
    .axis {{ fill: {DIM}; font-size: 11px; }}
    .grid {{ stroke: {FAINT}; stroke-dasharray: 2 4; }}
    .line {{ fill: none; stroke: {GREEN}; stroke-width: 2; stroke-linejoin: round;
             stroke-dasharray: {length:.0f}; stroke-dashoffset: {length:.0f};
             animation: draw 2s ease-out 0.3s forwards; filter: url(#glow); }}
    @keyframes draw {{ to {{ stroke-dashoffset: 0; }} }}
    .area {{ fill: url(#fade); opacity: 0; animation: show 0.8s ease-out 1.8s forwards; }}
    .pt {{ fill: {BG}; stroke: {GREEN}; stroke-width: 1.5; opacity: 0; animation: show 0.4s 2.1s forwards; }}
    @keyframes show {{ to {{ opacity: 1; }} }}
    @media (prefers-reduced-motion: reduce) {{
      .rain {{ display: none; }}
      .line {{ animation: none; stroke-dashoffset: 0; }}
      .area, .pt {{ animation: none; opacity: 1; }}
    }}
  </style>
  <defs>
    <clipPath id="ca"><rect width="{W}" height="{H}" rx="6"/></clipPath>
    <linearGradient id="fade" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{GREEN}" stop-opacity="0.28"/>
      <stop offset="1" stop-color="{GREEN}" stop-opacity="0"/>
    </linearGradient>
    <filter id="glow" x="-5%" y="-20%" width="110%" height="140%">
      <feGaussianBlur stdDeviation="2.5" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <g clip-path="url(#ca)">
    <rect width="{W}" height="{H}" fill="{BG}"/>
    {rain(W, H, 30, 2)}
    <rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="6" fill="none" stroke="{DIM}"/>
    <text x="{L}" y="32" class="title">Contributions, last 31 days</text>
    <text x="{W - R}" y="32" class="sub" text-anchor="end">{total} total  /  best day {best}</text>
    {"".join(grid)}
    {"".join(xlabels)}
    <path d="{area}" class="area"/>
    <path d="{path}" class="line"/>
    {dots}
  </g>
</svg>'''


def main():
    data = demo() if "--demo" in sys.argv else fetch()
    os.makedirs(OUT, exist_ok=True)
    with open(f"{OUT}/stats.svg", "w", encoding="utf-8") as f:
        f.write(stats_svg(data))
    with open(f"{OUT}/activity.svg", "w", encoding="utf-8") as f:
        f.write(activity_svg(data))
    print(f"Wrote {OUT}/stats.svg and {OUT}/activity.svg")


if __name__ == "__main__":
    main()
