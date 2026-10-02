"""
Generates GitHub stats SVG cards for a profile README.

Outputs (in assets/):
  stats.svg     stats with rank ring
  langs.svg     most used languages
  streak.svg    total contributions, current streak, longest streak
  activity.svg  contribution line graph (last 31 days)
  header.svg    animated intro header
  tech.svg      tech stack
  motto.svg     motto as a code window
  Each card also gets a -light.svg version for GitHub's light mode.

Env vars:
  GH_TOKEN  GitHub token (the workflow passes this in)
  GH_USER   GitHub username
  THEME     "purple" (default), "cyan" or "matrix"
Run with --demo to render sample data without calling the API.
"""
import json, os, sys, random, urllib.request
from datetime import date, timedelta
from xml.sax.saxutils import escape

USER = os.environ.get("GH_USER", "userMarcPaul")
TOKEN = os.environ.get("GH_TOKEN", "")
OUT = "assets"

THEMES = {
    "cyan": {
        "bg": "#0d1117", "title": "#00e5ff", "text": "#ffffff", "muted": "#9e9e9e",
        "icon": "#00e5ff", "ring": "#00e5ff", "fire": "#ff6e6e", "grid": "#21262d",
        "font": "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif",
        "lang_colors": None,  # use each language's real GitHub color
        "label_size": 14, "value_x": 255,
    },
    "purple": {
        "bg": "#0d1117", "title": "#c084fc", "text": "#ffffff", "muted": "#a1a1b5",
        "icon": "#c084fc", "ring": "#a855f7", "fire": "#f472b6", "grid": "#2a2140",
        "font": "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif",
        "lang_colors": ["#a855f7", "#f0abfc", "#6d28d9", "#e879f9", "#818cf8", "#ddd6fe"],
        "label_size": 14, "value_x": 255,
    },
    "purple-light": {
        "bg": "#ffffff", "title": "#7c3aed", "text": "#1f2328", "muted": "#59636e",
        "icon": "#7c3aed", "ring": "#8b5cf6", "fire": "#db2777", "grid": "#e9e3f7",
        "font": "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif",
        "lang_colors": ["#7c3aed", "#c026d3", "#4c1d95", "#e879f9", "#6366f1", "#c4b5fd"],
        "label_size": 14, "value_x": 255,
        "panel": "#f6f8fa", "subtext": "#3d3d4e", "lineno": "#a8a8bd", "is_light": True,
    },
    "cyan-light": {
        "bg": "#ffffff", "title": "#0891b2", "text": "#1f2328", "muted": "#59636e",
        "icon": "#0891b2", "ring": "#06b6d4", "fire": "#e5534b", "grid": "#d8f1f6",
        "font": "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif",
        "lang_colors": None,
        "label_size": 14, "value_x": 255,
        "panel": "#f6f8fa", "subtext": "#3d3d4e", "lineno": "#a8a8bd", "is_light": True,
    },
    "matrix": {
        "bg": "#000000", "title": "#00ff41", "text": "#00e03a", "muted": "#0f7a2a",
        "icon": "#00ff41", "ring": "#00ff41", "fire": "#00ff41", "grid": "#063d14",
        "font": "'Courier New', Consolas, 'Liberation Mono', monospace",
        "lang_colors": ["#00ff41", "#00cc34", "#009926", "#00661a", "#2bff6a", "#7dffa2"],
        "label_size": 13, "value_x": 274,
    },
}
THEME_NAME = os.environ.get("THEME", "purple")
if THEME_NAME not in THEMES:
    THEME_NAME = "purple"
# Light-mode partner for each theme (matrix has no light version, so it's used for both)
LIGHT_OF = {"purple": "purple-light", "cyan": "cyan-light", "matrix": "matrix"}
T = THEMES[THEME_NAME]
TODAY = date.today()

# ---------------------------------------------------------------- data

MAIN_QUERY = """
query($login: String!) {
  user(login: $login) {
    login
    followers { totalCount }
    pullRequests(first: 1) { totalCount }
    issues(first: 1) { totalCount }
    repositoriesContributedTo(first: 1, contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]) { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100,
                 orderBy: {field: STARGAZERS, direction: DESC}) {
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestReviewContributions
      contributionYears
    }
  }
}
"""


def gql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json",
                 "User-Agent": "readme-stats"},
    )
    with urllib.request.urlopen(req) as r:
        payload = json.load(r)
    if "errors" in payload:
        sys.exit(f"GitHub API error: {payload['errors']}")
    return payload["data"]


def fetch():
    u = gql(MAIN_QUERY, {"login": USER})["user"]
    cc = u["contributionsCollection"]

    # Pull every year's calendar so streaks and totals cover the whole account
    parts = [
        f'y{y}: contributionsCollection(from: "{y}-01-01T00:00:00Z", to: "{y}-12-31T23:59:59Z") '
        "{ contributionCalendar { weeks { contributionDays { date contributionCount } } } }"
        for y in cc["contributionYears"]
    ]
    cal = gql("query($login: String!) { user(login: $login) { " + " ".join(parts) + " } }",
              {"login": USER})["user"]
    by_date = {}
    for year in cal.values():
        for w in year["contributionCalendar"]["weeks"]:
            for d in w["contributionDays"]:
                by_date[d["date"]] = d["contributionCount"]

    langs = {}
    for repo in u["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            name = e["node"]["name"]
            size, color = langs.get(name, (0, e["node"]["color"]))
            langs[name] = (size + e["size"], color)

    return {
        "login": u["login"],
        "stars": sum(r["stargazerCount"] for r in u["repositories"]["nodes"]),
        "commits": cc["totalCommitContributions"],
        "reviews": cc["totalPullRequestReviewContributions"],
        "prs": u["pullRequests"]["totalCount"],
        "issues": u["issues"]["totalCount"],
        "contributed": u["repositoriesContributedTo"]["totalCount"],
        "followers": u["followers"]["totalCount"],
        "days": by_date,
        "langs": langs,
    }


def demo():
    random.seed(7)
    days = {}
    start = TODAY - timedelta(days=330)
    for i in range(331):
        d = start + timedelta(days=i)
        days[d.isoformat()] = max(0, int(random.gauss(1.2, 2.2)))
    return {"login": USER, "stars": 10, "commits": 64, "reviews": 3, "prs": 40, "issues": 0,
            "contributed": 4, "followers": 12, "days": days,
            "langs": {"JavaScript": (52000, "#f1e05a"), "TypeScript": (31000, "#3178c6"),
                      "Python": (18000, "#3572A5"), "Java": (12000, "#b07219"),
                      "Dart": (9000, "#00B4AB"), "CSS": (6000, "#563d7c"), "HTML": (4000, "#e34c26")}}

# ---------------------------------------------------------------- helpers


def kfmt(n):
    return f"{n / 1000:.1f}k".replace(".0k", "k") if n >= 1000 else str(n)


def fmt_day(d):
    s = f"{d.strftime('%b')} {d.day}"
    return s if d.year == TODAY.year else f"{s}, {d.year}"


def fmt_range(a, b):
    return fmt_day(a) if a == b else f"{fmt_day(a)} - {fmt_day(b)}"


def rank(d):
    """Same scoring idea as github-readme-stats: weighted percentiles, lower is better."""
    def exp_cdf(x): return 1 - 2 ** -x
    def log_cdf(x): return x / (1 + x)
    parts = [
        (2, exp_cdf(d["commits"] / 250)),
        (3, exp_cdf(d["prs"] / 50)),
        (1, exp_cdf(d["issues"] / 25)),
        (1, exp_cdf(d["reviews"] / 2)),
        (4, log_cdf(d["stars"] / 50)),
        (1, log_cdf(d["followers"] / 10)),
    ]
    pct = (1 - sum(w * v for w, v in parts) / sum(w for w, _ in parts)) * 100
    levels = [(1, "S"), (12.5, "A+"), (25, "A"), (37.5, "A-"), (50, "B+"),
              (62.5, "B"), (75, "B-"), (87.5, "C+"), (100, "C")]
    level = next(l for t, l in levels if pct <= t)
    return level, pct


def streaks(by_date):
    days = sorted((date.fromisoformat(k), v) for k, v in by_date.items()
                  if date.fromisoformat(k) <= TODAY)
    if not days:
        return {"total": 0, "first": TODAY, "cur": 0, "cur_range": (TODAY, TODAY),
                "long": 0, "long_range": (TODAY, TODAY)}
    total = sum(v for _, v in days)
    first = next((d for d, v in days if v > 0), TODAY)

    best, best_rng, run, run_start = 0, (TODAY, TODAY), 0, None
    for d, v in days:
        if v > 0:
            run_start = d if run == 0 else run_start
            run += 1
            if run > best:
                best, best_rng = run, (run_start, d)
        else:
            run = 0

    # Today with no contributions yet doesn't break the streak
    i = len(days) - 1
    if days[i][1] == 0:
        i -= 1
    cur, end = 0, days[i][0] if i >= 0 else TODAY
    while i >= 0 and days[i][1] > 0:
        cur += 1
        i -= 1
    cur_rng = (end - timedelta(days=cur - 1), end) if cur else (TODAY, TODAY)
    return {"total": total, "first": first, "cur": cur, "cur_range": cur_rng,
            "long": best, "long_range": best_rng}


def rain(width, height, cols, seed):
    if T is not THEMES["matrix"]:
        return ""
    rnd = random.Random(seed)
    glyphs = "ｱｲｳｴｵｶｷｸｹｺ01ﾊﾐﾋｰｳｼﾅﾓﾆｻﾜﾂｵﾘ"
    out = []
    for i in range(cols):
        x = int((i + 0.5) * width / cols)
        chars = "".join(f'<tspan x="{x}" dy="14">{rnd.choice(glyphs)}</tspan>' for _ in range(rnd.randint(6, 12)))
        dur = rnd.uniform(6, 12)
        out.append(f'<text class="rain" style="animation-duration:{dur:.1f}s;'
                   f'animation-delay:{-rnd.uniform(0, dur):.1f}s" y="-200">{chars}</text>')
    return "\n".join(out)


def frame(W, H, title, body, extra_css=""):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{escape(title)}">
<title>{escape(title)}</title>
<style>
  text {{ font-family: {T["font"]}; }}
  .title {{ fill: {T["title"]}; font-size: 18px; font-weight: 600; }}
  .rain {{ fill: {T["grid"]}; opacity: 0.6; font-size: 13px; animation: fall linear infinite; }}
  @keyframes fall {{ to {{ transform: translateY({H + 400}px); }} }}
  .fade {{ opacity: 0; animation: fadein 0.4s ease-out forwards; }}
  @keyframes fadein {{ to {{ opacity: 1; }} }}
  {extra_css}
  @media (prefers-reduced-motion: reduce) {{
    .rain {{ display: none; }}
    * {{ animation: none !important; opacity: 1 !important; }}
  }}
</style>
<clipPath id="card-{W}x{H}"><rect width="{W}" height="{H}" rx="4.5"/></clipPath>
<g clip-path="url(#card-{W}x{H})">
<rect width="{W}" height="{H}" fill="{T["bg"]}"/>
{rain(W, H, max(8, W // 28), W + H)}
{body}
</g>
</svg>'''

# ---------------------------------------------------------------- icons (16x16, stroked)


def star_points():
    import math
    pts = []
    for k in range(10):
        r = 7 if k % 2 == 0 else 3.1
        a = math.radians(-90 + k * 36)
        pts.append(f"{8 + r * math.cos(a):.2f},{8.6 + r * math.sin(a):.2f}")
    return " ".join(pts)


ICONS = {
    "star": f'<polygon points="{star_points()}" stroke-linejoin="round"/>',
    "commits": '<path d="M2.2 8a5.8 5.8 0 1 0 1.7-4.1"/><path d="M1.6 2.2v2.6h2.6"/><path d="M8 4.8V8l2.3 1.5"/>',
    "prs": '<circle cx="4" cy="3.5" r="1.7"/><circle cx="4" cy="12.5" r="1.7"/><circle cx="12" cy="12.5" r="1.7"/>'
           '<path d="M4 5.2v5.6"/><path d="M12 10.8V6.3a2 2 0 0 0-2-2H7.4"/><path d="M8.9 2.7 7.3 4.3l1.6 1.6"/>',
    "issues": '<circle cx="8" cy="8" r="6.3"/><circle cx="8" cy="8" r="1.1" fill="currentColor"/>',
    "repo": '<path d="M3 13V3a1.5 1.5 0 0 1 1.5-1.5H13v10H4.5A1.5 1.5 0 0 0 3 13a1.5 1.5 0 0 0 1.5 1.5H13"/>'
            '<path d="M6 11.5v3.5l1.25-.9 1.25.9v-3.5"/>',
}


def icon(name, x, y):
    return (f'<g transform="translate({x},{y})" fill="none" stroke="{T["icon"]}" color="{T["icon"]}" '
            f'stroke-width="1.4" stroke-linecap="round">{ICONS[name]}</g>')

# ---------------------------------------------------------------- cards


def stats_svg(d):
    W, H = 440, 195
    level, pct = rank(d)
    rows = [
        ("star", "Total Stars Earned:", d["stars"]),
        ("commits", "Total Commits (last year):", d["commits"]),
        ("prs", "Total PRs:", d["prs"]),
        ("issues", "Total Issues:", d["issues"]),
        ("repo", "Contributed to (last year):", d["contributed"]),
    ]
    body = [f'<text x="25" y="35" class="title">{escape(d["login"])}\'s GitHub Stats</text>']
    for i, (ic, label, val) in enumerate(rows):
        y = 65 + i * 25
        body.append(
            f'<g class="fade" style="animation-delay:{0.15 + i * 0.12:.2f}s">'
            f'{icon(ic, 25, y - 12)}'
            f'<text x="50" y="{y}" class="label">{escape(label)}</text>'
            f'<text x="{T["value_x"]}" y="{y}" class="label">{kfmt(val)}</text></g>')
    r = 40
    circ = 2 * 3.14159265 * r
    filled = circ * (100 - pct) / 100
    cx, cy = 360, 105
    body.append(
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{T["ring"]}" stroke-opacity="0.2" stroke-width="6"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{T["ring"]}" stroke-width="6" stroke-linecap="round" '
        f'class="ring" transform="rotate(-90 {cx} {cy})"/>'
        f'<text x="{cx}" y="{cy}" class="level" text-anchor="middle" dominant-baseline="central">{level}</text>')
    css = f'''.label {{ fill: {T["text"]}; font-size: {T["label_size"]}px; font-weight: 600; }}
  .level {{ fill: {T["text"]}; font-size: 24px; font-weight: 800; }}
  .ring {{ stroke-dasharray: {circ:.2f}; stroke-dashoffset: {circ - filled:.2f};
           animation: ringfill 1s ease-out forwards; }}
  @keyframes ringfill {{ from {{ stroke-dashoffset: {circ:.2f}; }} }}'''
    return frame(W, H, f"GitHub stats for {d['login']}", "\n".join(body), css)


def langs_svg(d):
    W, H = 380, 195
    top = sorted(d["langs"].items(), key=lambda kv: -kv[1][0])[:6]
    total = sum(v[0] for _, v in top) or 1
    colors = [T["lang_colors"][i] if T["lang_colors"] else (c or "#858585")
              for i, (_, (_, c)) in enumerate(top)]
    bar_w, bx, by = W - 50, 25, 55
    body = [f'<text x="25" y="35" class="title">Most Used Languages</text>',
            f'<clipPath id="bar"><rect x="{bx}" y="{by}" width="{bar_w}" height="8" rx="4"/></clipPath>',
            f'<g clip-path="url(#bar)" class="grow">']
    x = bx
    for i, (_, (size, _)) in enumerate(top):
        w = bar_w * size / total
        body.append(f'<rect x="{x:.2f}" y="{by}" width="{w + 0.5:.2f}" height="8" fill="{colors[i]}"/>')
        x += w
    body.append("</g>")
    for i, (name, (size, _)) in enumerate(top):
        col, row = i % 2, i // 2
        lx, ly = 25 + col * 170, 95 + row * 28
        body.append(
            f'<g class="fade" style="animation-delay:{0.3 + i * 0.1:.2f}s">'
            f'<circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{colors[i]}"/>'
            f'<text x="{lx + 17}" y="{ly}" class="lang">{escape(name)} {size / total * 100:.2f}%</text></g>')
    css = f'''.lang {{ fill: {T["text"]}; font-size: 12px; }}
  .grow {{ transform-origin: {bx}px {by}px; animation: grow 0.8s ease-out; }}
  @keyframes grow {{ from {{ transform: scaleX(0); }} }}'''
    return frame(W, H, f"Most used languages for {d['login']}", "\n".join(body), css)


def streak_svg(d):
    W, H = 495, 195
    s = streaks(d["days"])
    c1, c2, c3 = W / 6, W / 2, W * 5 / 6
    cur_label = fmt_day(TODAY) if s["cur"] == 0 else fmt_range(*s["cur_range"])
    long_label = "No streak yet" if s["long"] == 0 else fmt_range(*s["long_range"])
    flame = ('<path d="M0 -11 C1.5 -7 7 -4.5 7 1.5 A7 7 0 0 1 -7 1.5 C-7 -2.5 -4.5 -5 -3.5 -7.5 '
             'C-2.5 -5 -1.5 -4 -0.5 -3.5 C-0.5 -6.5 -1 -9 0 -11 Z" />'
             '<path d="M0 -1.5 C1 0.5 3 1.5 3 3.5 A3 3 0 0 1 -3 3.5 C-3 1.8 -1.5 0.8 0 -1.5 Z" fill="' + T["bg"] + '"/>')
    cy = 72
    body = f'''
<g class="fade" style="animation-delay:0.2s">
  <text x="{c1}" y="{cy + 10}" class="num" text-anchor="middle">{kfmt(s["total"])}</text>
  <text x="{c1}" y="{cy + 50}" class="lab" text-anchor="middle">Total Contributions</text>
  <text x="{c1}" y="{cy + 78}" class="date" text-anchor="middle">{escape(fmt_day(s["first"]))} - Present</text>
</g>
<mask id="gap"><rect width="{W}" height="{H}" fill="white"/><circle cx="{c2}" cy="{cy - 40}" r="13" fill="black"/></mask>
<circle cx="{c2}" cy="{cy}" r="40" fill="none" stroke="{T["ring"]}" stroke-width="5" mask="url(#gap)" class="ringin"/>
<g transform="translate({c2},{cy - 40})" fill="{T["fire"]}" class="fade" style="animation-delay:0.6s">{flame}</g>
<g class="fade" style="animation-delay:0.4s">
  <text x="{c2}" y="{cy + 10}" class="num" text-anchor="middle">{s["cur"]}</text>
  <text x="{c2}" y="{cy + 64}" class="cur" text-anchor="middle">Current Streak</text>
  <text x="{c2}" y="{cy + 88}" class="date" text-anchor="middle">{escape(cur_label)}</text>
</g>
<g class="fade" style="animation-delay:0.6s">
  <text x="{c3}" y="{cy + 10}" class="num" text-anchor="middle">{s["long"]}</text>
  <text x="{c3}" y="{cy + 50}" class="lab" text-anchor="middle">Longest Streak</text>
  <text x="{c3}" y="{cy + 78}" class="date" text-anchor="middle">{escape(long_label)}</text>
</g>'''
    css = f'''.num {{ fill: {T["text"]}; font-size: 28px; font-weight: 700; }}
  .lab {{ fill: {T["text"]}; font-size: 14px; }}
  .cur {{ fill: {T["ring"]}; font-size: 14px; font-weight: 700; }}
  .date {{ fill: {T["muted"]}; font-size: 12px; }}
  .ringin {{ transform-origin: {c2}px {cy}px; animation: pop 0.6s ease-out; }}
  @keyframes pop {{ from {{ transform: scale(0.6); opacity: 0; }} }}'''
    return frame(W, H, f"Contribution streaks for {d['login']}", body, css)


def activity_svg(d):
    items = sorted(d["days"].items())
    items = [(k, v) for k, v in items if date.fromisoformat(k) <= TODAY][-31:]
    W, H = 850, 300
    L, R, Tp, B = 56, 24, 64, 46
    pw, ph = W - L - R, H - Tp - B
    counts = [v for _, v in items]
    step = max(1, -(-max(max(counts), 4) // 4))
    ymax = step * 4

    def px(i): return L + pw * i / (len(items) - 1)
    def py(v): return Tp + ph - ph * v / ymax

    pts = [(px(i), py(c)) for i, c in enumerate(counts)]
    path = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = path + f" L{pts[-1][0]:.1f},{Tp + ph} L{pts[0][0]:.1f},{Tp + ph} Z"
    length = sum(((pts[i + 1][0] - pts[i][0]) ** 2 + (pts[i + 1][1] - pts[i][1]) ** 2) ** 0.5
                 for i in range(len(pts) - 1))
    grid = "".join(
        f'<line x1="{L}" y1="{py(step * k):.1f}" x2="{W - R}" y2="{py(step * k):.1f}" class="grid"/>'
        f'<text x="{L - 10}" y="{py(step * k) + 4:.1f}" class="axis" text-anchor="end">{step * k}</text>'
        for k in range(5))
    xl = "".join(
        f'<text x="{px(i):.1f}" y="{H - B + 22}" class="axis" text-anchor="middle">{fmt_day(date.fromisoformat(items[i][0]))}</text>'
        for i in range(0, len(items), 5))
    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" class="pt"><title>{items[i][0]}: {counts[i]}</title></circle>'
        for i, (x, y) in enumerate(pts))
    body = f'''
<defs><linearGradient id="fade-area" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="{T["ring"]}" stop-opacity="0.3"/><stop offset="1" stop-color="{T["ring"]}" stop-opacity="0"/>
</linearGradient></defs>
<text x="{L}" y="35" class="title">Contributions, last 31 days</text>
<text x="{W - R}" y="35" class="sub" text-anchor="end">{sum(counts)} total  /  best day {max(counts)}</text>
{grid}{xl}
<path d="{area}" class="area"/>
<path d="{path}" class="line"/>
{dots}'''
    css = f'''.sub {{ fill: {T["muted"]}; font-size: 12px; }}
  .axis {{ fill: {T["muted"]}; font-size: 11px; }}
  .grid {{ stroke: {T["grid"]}; stroke-dasharray: 3 4; }}
  .line {{ fill: none; stroke: {T["ring"]}; stroke-width: 2.5; stroke-linejoin: round;
           stroke-dasharray: {length:.0f}; stroke-dashoffset: {length:.0f}; animation: draw 2s ease-out 0.3s forwards; }}
  @keyframes draw {{ to {{ stroke-dashoffset: 0; }} }}
  .area {{ fill: url(#fade-area); opacity: 0; animation: fadein 0.8s ease-out 1.8s forwards; }}
  .pt {{ fill: {T["bg"]}; stroke: {T["ring"]}; stroke-width: 2; opacity: 0; animation: fadein 0.4s 2.1s forwards; }}
  @media (prefers-reduced-motion: reduce) {{ .line {{ stroke-dashoffset: 0; }} }}'''
    return frame(W, H, f"Contributions in the last 31 days for {d['login']}", body, css)


# ---------------------------------------------------------------- profile content
# Edit these to change what the header, tech stack and motto show.

NAME = "marcxdev"
TAGLINES = ["Just a developer", "Learning the MERN stack", "Building apps with Flutter"]

DEVICON = "https://raw.githubusercontent.com/devicons/devicon/master/icons"
# (name shown, devicon file, True if the logo is dark and should be drawn light)
TECH = [
    ("Languages", [
        ("Java", "java/java-original", False),
        ("JavaScript", "javascript/javascript-original", False),
        ("TypeScript", "typescript/typescript-original", False),
        ("Python", "python/python-original", False),
        ("Ruby", "ruby/ruby-original", False),
        ("C", "c/c-original", False),
        ("C++", "cplusplus/cplusplus-original", False),
        ("C#", "csharp/csharp-original", False),
    ]),
    ("Frontend", [
        ("HTML", "html5/html5-original", False),
        ("CSS", "css3/css3-original", False),
        ("React", "react/react-original", False),
    ]),
    ("Backend", [
        ("Node.js", "nodejs/nodejs-original", False),
        ("Express", "express/express-original", True),
        ("Django", "django/django-plain", True),
        ("Rails", "rails/rails-plain", False),
    ]),
    ("Mobile", [
        ("Flutter", "flutter/flutter-original", False),
        ("Dart", "dart/dart-original", False),
    ]),
    ("Databases", [
        ("PostgreSQL", "postgresql/postgresql-original", False),
        ("MySQL", "mysql/mysql-original", False),
        ("MongoDB", "mongodb/mongodb-original", False),
    ]),
]

MOTTO = [
    [("kw", "while"), ("p", " ("), ("v", "alive"), ("p", ") {")],
    [("p", "  "), ("fn", "code"), ("p", "();")],
    [("p", "  "), ("fn", "learn"), ("p", "();")],
    [("p", "  "), ("fn", "repeat"), ("p", "();")],
    [("p", "}")],
]

MONO = "'JetBrains Mono', 'Fira Code', Consolas, 'Courier New', monospace"
ICON_OVERRIDE = {}  # used by the local preview only
_ICON_CACHE = {}


def icon_data_uri(path, offline):
    """Logos are embedded in the SVG itself, because an SVG shown as an image can't load other files."""
    import base64
    if path in ICON_OVERRIDE:
        return ICON_OVERRIDE[path]
    if path in _ICON_CACHE:
        return _ICON_CACHE[path]
    if offline:
        return None
    try:
        with urllib.request.urlopen(f"{DEVICON}/{path}.svg", timeout=20) as r:
            raw = r.read()
        _ICON_CACHE[path] = "data:image/svg+xml;base64," + base64.b64encode(raw).decode()
        return _ICON_CACHE[path]
    except Exception as e:
        print(f"  could not load {path}: {e}")
        return None


def hero_svg():
    W, H = 850, 210
    acc, acc2 = T["ring"], T["fire"]
    n = len(TAGLINES)
    slot = 3.2
    cycle = slot * n
    cw = 11.4  # monospace char width at 19px
    lines = []
    for i, t in enumerate(TAGLINES):
        w = len(t) * cw
        d = i * slot
        left = W / 2 - (w + 26) / 2 + 26
        lines.append(
            f'<g class="tag" style="animation-delay:{d:.1f}s" transform="translate({left:.1f},166)">'
            f'<text x="-26" y="0" class="prompt">&gt;</text>'
            f'<clipPath id="type{i}"><rect x="0" y="-22" width="{w + 2:.0f}" height="30" class="typer" style="animation-delay:{d:.1f}s;animation-timing-function:steps({len(t)})"/></clipPath>'
            f'<text class="typed" clip-path="url(#type{i})" textLength="{w:.1f}" lengthAdjust="spacing">{escape(t)}</text>'
            f'<rect x="0" y="-16" width="10" height="20" class="caret" style="--w:{w + 4:.0f}px;animation-delay:{d:.1f}s, 0s;animation-timing-function:steps({len(t)}), steps(1)"/></g>')
    a = 100 / n
    css = f'''.hi {{ fill: {T["muted"]}; font-size: 18px; }}
  .name {{ font-size: 52px; font-weight: 800; letter-spacing: -1px; }}
  .prompt {{ fill: {acc}; font-family: {MONO}; font-size: 19px; font-weight: 700; }}
  .typed {{ fill: {T["text"]}; font-family: {MONO}; font-size: 19px; }}
  .tag {{ opacity: 0; animation: slotvis {cycle:.1f}s infinite; }}
  @keyframes slotvis {{ 0% {{ opacity: 1; }} {a * 0.97:.2f}% {{ opacity: 1; }} {a:.2f}%, 100% {{ opacity: 0; }} }}
  .typer {{ transform: scaleX(0); animation: type {cycle:.1f}s steps(24) infinite; }}
  @keyframes type {{ 0% {{ transform: scaleX(0); }} {a * 0.42:.2f}%, 100% {{ transform: scaleX(1); }} }}
  .caret {{ fill: {acc}; opacity: 0.85; animation: move {cycle:.1f}s steps(24) infinite, blink 0.9s steps(1) infinite; }}
  @keyframes move {{ 0% {{ transform: translateX(0); }} {a * 0.42:.2f}%, 100% {{ transform: translateX(var(--w)); }} }}
  @keyframes blink {{ 50% {{ fill-opacity: 0; }} }}
  .glow {{ animation: drift 10s ease-in-out infinite alternate; }}
  @keyframes drift {{ to {{ transform: translateX(90px); }} }}
  @media (prefers-reduced-motion: reduce) {{
    .tag:first-of-type {{ opacity: 1 !important; }}
    .tag:not(:first-of-type) {{ display: none; }}
    .typer {{ transform: none; }}
  }}'''
    body = f'''<defs>
  <radialGradient id="g1" cx="0.5" cy="0.5" r="0.5">
    <stop offset="0" stop-color="{acc}" stop-opacity="0.28"/><stop offset="1" stop-color="{acc}" stop-opacity="0"/>
  </radialGradient>
  <radialGradient id="g2" cx="0.5" cy="0.5" r="0.5">
    <stop offset="0" stop-color="{acc2}" stop-opacity="0.16"/><stop offset="1" stop-color="{acc2}" stop-opacity="0"/>
  </radialGradient>
  <linearGradient id="namefill" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="{T["title"]}"/><stop offset="1" stop-color="{acc2}"/>
  </linearGradient>
</defs>
<ellipse cx="330" cy="105" rx="300" ry="100" fill="url(#g1)" class="glow"/>
<ellipse cx="560" cy="115" rx="240" ry="90" fill="url(#g2)"/>
<text x="{W / 2}" y="62" class="hi" text-anchor="middle">Hi, I'm</text>
<text x="{W / 2}" y="118" class="name" text-anchor="middle" fill="url(#namefill)">{escape(NAME)}</text>
{"".join(lines)}'''
    return frame(W, H, f"Hi, I'm {NAME}", body, css)


TECH_ROWS = [["Languages"], ["Frontend", "Backend"], ["Mobile", "Databases"]]


def tech_svg(offline=False):
    W = 850
    slot, tile = 80, 56
    gap = 72
    row_h = 132
    top = 24
    groups = dict(TECH)
    H = top + row_h * len(TECH_ROWS) - 4
    body = ['<filter id="light"><feColorMatrix type="matrix" values="0 0 0 0 0.92  0 0 0 0 0.9  0 0 0 0 0.97  0 0 0 1 0"/></filter>']
    k = 0
    for r, names in enumerate(TECH_ROWS):
        y = top + r * row_h
        widths = [len(groups[n]) * slot for n in names]
        x = (W - (sum(widths) + gap * (len(names) - 1))) / 2
        for gi, name in enumerate(names):
            items = groups[name]
            gx = x
            if gi:
                body.append(f'<line x1="{gx - gap / 2:.1f}" y1="{y + 4}" x2="{gx - gap / 2:.1f}" y2="{y + 108}" class="sep"/>')
            body.append(f'<text x="{gx + (slot - tile) / 2:.1f}" y="{y + 14}" class="group">{escape(name)}'
                        f'<tspan class="count" dx="8">{len(items)}</tspan></text>')
            for j, (tname, path, light) in enumerate(items):
                tx = gx + j * slot + (slot - tile) / 2
                ty = y + 28
                uri = icon_data_uri(path, offline)
                if uri:
                    filt = ' filter="url(#light)"' if light and not T.get("is_light") else ""
                    img = f'<image x="{tx + 12:.1f}" y="{ty + 12}" width="32" height="32" href="{uri}" xlink:href="{uri}"{filt}/>'
                else:
                    img = f'<text x="{tx + tile / 2:.1f}" y="{ty + 34}" class="init" text-anchor="middle">{escape(tname[:2])}</text>'
                body.append(
                    f'<g class="fade" style="animation-delay:{0.05 + k * 0.03:.2f}s">'
                    f'<rect x="{tx:.1f}" y="{ty}" width="{tile}" height="{tile}" rx="14" class="tile"/>{img}'
                    f'<text x="{tx + tile / 2:.1f}" y="{ty + tile + 18}" class="tname" text-anchor="middle">{escape(tname)}</text></g>')
                k += 1
            x += widths[gi] + gap
    css = f'''.group {{ fill: {T["title"]}; font-size: 15px; font-weight: 700; }}
  .count {{ fill: {T["muted"]}; font-size: 12px; font-weight: 400; }}
  .tile {{ fill: {T.get("panel", "#161b22")}; stroke: {T["grid"]}; stroke-width: 1; }}
  .tname {{ fill: {T.get("subtext", "#c9c9d9")}; font-size: 11.5px; }}
  .init {{ fill: {T["title"]}; font-size: 16px; font-weight: 700; }}
  .sep {{ stroke: {T["grid"]}; stroke-width: 1; }}'''
    svg = frame(W, H, "Tech stack", "\n".join(body), css)
    return svg.replace('xmlns="http://www.w3.org/2000/svg"',
                       'xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"', 1)


def motto_svg():
    W = 520
    lh = 26
    H = 58 + lh * len(MOTTO) + 22
    colors = {"kw": T["fire"], "fn": T["title"], "v": T["text"], "p": T["muted"]}
    rows = []
    for i, line in enumerate(MOTTO):
        y = 72 + i * lh
        spans = "".join(f'<tspan fill="{colors[c]}">{escape(t)}</tspan>' for c, t in line)
        rows.append(f'<text x="34" y="{y}" class="ln" text-anchor="end">{i + 1}</text>'
                    f'<text x="52" y="{y}" class="code" xml:space="preserve">{spans}</text>')
    last_y = 72 + (len(MOTTO) - 1) * lh
    body = f'''<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="10" fill="none" stroke="{T["grid"]}"/>
<rect x="1" y="1" width="{W - 2}" height="34" rx="9" fill="{T.get("panel", "#161b22")}"/>
<rect x="1" y="26" width="{W - 2}" height="9" fill="{T.get("panel", "#161b22")}"/>
<line x1="1" y1="35" x2="{W - 1}" y2="35" stroke="{T["grid"]}"/>
<circle cx="22" cy="18" r="5.5" fill="#ff5f57"/><circle cx="40" cy="18" r="5.5" fill="#febc2e"/><circle cx="58" cy="18" r="5.5" fill="#28c840"/>
<text x="{W / 2}" y="22" class="file" text-anchor="middle">motto.js</text>
{"".join(rows)}
<rect x="66" y="{last_y - 15}" width="9" height="19" class="caret"/>'''
    css = f'''.file {{ fill: {T["muted"]}; font-size: 12.5px; }}
  .ln {{ fill: {T.get("lineno", "#4b4b63")}; font-family: {MONO}; font-size: 15px; }}
  .code {{ font-family: {MONO}; font-size: 16px; }}
  .caret {{ fill: {T["ring"]}; animation: blink 1s steps(1) infinite; }}
  @keyframes blink {{ 50% {{ opacity: 0; }} }}'''
    return frame(W, H, "Motto", body, css)


def main():
    global T
    offline = "--demo" in sys.argv
    data = demo() if offline else fetch()
    os.makedirs(OUT, exist_ok=True)
    cards = [("stats", lambda: stats_svg(data)), ("langs", lambda: langs_svg(data)),
             ("streak", lambda: streak_svg(data)), ("activity", lambda: activity_svg(data)),
             ("header", hero_svg), ("tech", lambda: tech_svg(offline)), ("motto", motto_svg)]
    # name.svg is the dark version, name-light.svg the light one
    for suffix, theme in [("", THEME_NAME), ("-light", LIGHT_OF.get(THEME_NAME, THEME_NAME))]:
        T = THEMES[theme]
        for name, fn in cards:
            with open(f"{OUT}/{name}{suffix}.svg", "w", encoding="utf-8") as f:
                f.write(fn())
    print(f"Wrote dark and light versions of {', '.join(n for n, _ in cards)} to {OUT}/")


if __name__ == "__main__":
    main()
