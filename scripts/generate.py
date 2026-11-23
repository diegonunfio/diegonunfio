#!/usr/bin/env python3
"""
Genera las tarjetas estilo terminal del README de perfil de GitHub.

Lee profile.json, consulta los datos públicos de GitHub y escribe:
  assets/hero.svg      whoami + bio, con animación de tipeo
  assets/stack.svg     lenguajes (detectados de tus repos) y herramientas
  assets/projects.svg  tus repos más relevantes
  assets/activity.svg  mapa de contribuciones del último año

Sin dependencias: solo la librería estándar de Python 3.9+.

Uso local:
    python scripts/generate.py
    (opcional) export GITHUB_TOKEN=...   para evitar el límite de la API
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import textwrap
import urllib.request
from collections import Counter
from xml.sax.saxutils import escape as _escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
API = "https://api.github.com"

# ---------------------------------------------------------------- diseño ----
W = 860      # ancho del lienzo; GitHub lo escala con width="100%"
PAD = 32     # margen interior horizontal
BAR = 44     # alto de la barra de título
FS = 15      # tamaño base del texto
CH = 0.6     # ancho aproximado de un carácter monoespaciado, en em
LH = 28      # alto de línea

FONT = ("ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, "
        "'Liberation Mono', 'DejaVu Sans Mono', monospace")

THEME = {
    "bg": "#0b0f14",
    "bar": "#131920",
    "border": "#262d38",
    "text": "#d6dde6",
    "muted": "#7b8696",
    "dim": "#4f5867",
    "chip": "#11161d",
    "chip_border": "#2a323e",
    "empty": "#161c24",
}

# Colores oficiales de GitHub Linguist para los lenguajes más comunes.
LANG_COLORS = {
    "C#": "#178600", "TypeScript": "#3178c6", "JavaScript": "#f1e05a",
    "Python": "#3572A5", "HCL": "#844FBA", "HTML": "#e34c26",
    "CSS": "#663399", "SCSS": "#c6538c", "Go": "#00ADD8", "Rust": "#dea584",
    "Java": "#b07219", "Kotlin": "#A97BFF", "Shell": "#89e051",
    "PowerShell": "#012456", "Dockerfile": "#384d54", "Vue": "#41b883",
    "Svelte": "#ff3e00", "Ruby": "#701516", "PHP": "#4F5D95", "C": "#555555",
    "C++": "#f34b7d", "Swift": "#F05138", "Dart": "#00B4AB",
    "Jupyter Notebook": "#DA5B0B", "TSQL": "#e38c00", "Bicep": "#519aba",
    "Makefile": "#427819", "Lua": "#000080", "Elixir": "#6e4a7e",
}


def esc(value) -> str:
    return _escape(str(value), {'"': "&quot;"})


def clip(text: str, n: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: max(n - 1, 0)].rstrip() + "…"


# ------------------------------------------------------------- datos -------
def load_profile() -> dict:
    path = os.path.join(ROOT, "profile.json")
    with open(path, encoding="utf-8") as f:
        p = json.load(f)
    if not p.get("username"):
        sys.exit("profile.json necesita al menos el campo \"username\".")
    p.setdefault("accent", "#33e37b")
    p.setdefault("accent2", "#4fa3ff")
    p.setdefault("skills", [])
    p.setdefault("projects", [])
    p.setdefault("hide_languages", [])
    p.setdefault("projects_limit", 6)
    if isinstance(p.get("bio"), list):
        p["bio"] = " ".join(s.strip() for s in p["bio"])
    return p


def http(url: str, token: str | None = None, payload: dict | None = None,
         raw: bool = False):
    headers = {"User-Agent": "profile-cards", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None
    if payload is not None:
        body = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        text = r.read().decode("utf-8")
    return text if raw else json.loads(text)


def fetch_repos(user: str, token: str | None) -> list[dict]:
    data = http(f"{API}/users/{user}/repos?per_page=100&type=owner&sort=pushed", token)
    return [
        {
            "name": r["name"],
            "language": r.get("language"),
            "stars": r.get("stargazers_count", 0),
            "pushed_at": r.get("pushed_at") or r.get("updated_at"),
            "description": r.get("description") or "",
        }
        for r in data
        if not r.get("fork") and not r.get("archived")
    ]


def fetch_calendar(user: str, token: str | None) -> dict:
    """Contribuciones del último año: GraphQL si hay token, si no la página pública."""
    if token:
        try:
            query = """query($login:String!){user(login:$login){contributionsCollection{
              contributionCalendar{totalContributions weeks{contributionDays{date contributionLevel}}}}}}"""
            res = http(f"{API}/graphql", token, {"query": query, "variables": {"login": user}})
            cal = res["data"]["user"]["contributionsCollection"]["contributionCalendar"]
            levels = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
                      "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
            days = [(d["date"], levels.get(d["contributionLevel"], 0))
                    for w in cal["weeks"] for d in w["contributionDays"]]
            return {"total": cal["totalContributions"], "days": days}
        except Exception as e:  # noqa: BLE001
            print(f"  GraphQL no disponible ({e}); uso la página pública.")
    page = http(f"https://github.com/users/{user}/contributions", raw=True)
    days = re.findall(r'data-date="(\d{4}-\d{2}-\d{2})"[^>]*?data-level="(\d)"', page)
    total = re.search(r"([\d,]+)\s+contributions?\s+in\s+the\s+last\s+year", page)
    if not days:
        raise RuntimeError("no encontré el calendario de contribuciones")
    return {
        "total": int(total.group(1).replace(",", "")) if total else 0,
        "days": [(d, int(l)) for d, l in days],
    }


# ------------------------------------------------------- piezas SVG --------
def window(title: str, label: str, body: str, height: float, p: dict,
           extra_css: str = "") -> str:
    t, h = THEME, round(height)
    css = f"""
    text {{ font-family: {FONT}; font-size: {FS}px; fill: {t['text']}; white-space: pre; }}
    .title {{ font-size: 13px; fill: {t['muted']}; }}
    .u {{ fill: {p['accent']}; font-weight: 600; }}
    .ps, .mut {{ fill: {t['muted']}; }}
    .dim {{ fill: {t['dim']}; }}
    .a1 {{ fill: {p['accent']}; }}
    .a2 {{ fill: {p['accent2']}; }}
    .sm {{ font-size: 13px; }}
    .xs {{ font-size: 12px; }}
    {extra_css}
    @media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; }} }}
    """
    r = 12
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" role="img" aria-labelledby="t">
<title id="t">{esc(label)}</title>
<style>{css}</style>
<rect x="0.5" y="0.5" width="{W - 1}" height="{h - 1}" rx="{r}" fill="{t['bg']}"/>
<path d="M0.5 {BAR}.5V{r}.5A{r} {r} 0 0 1 {r}.5 0.5H{W - r - 0.5}A{r} {r} 0 0 1 {W - 0.5} {r}.5V{BAR}.5Z" fill="{t['bar']}"/>
<line x1="0.5" y1="{BAR}.5" x2="{W - 0.5}" y2="{BAR}.5" stroke="{t['border']}"/>
<rect x="0.5" y="0.5" width="{W - 1}" height="{h - 1}" rx="{r}" fill="none" stroke="{t['border']}"/>
<circle cx="24" cy="22.5" r="6" fill="#ff5f57" fill-opacity=".85"/>
<circle cx="44" cy="22.5" r="6" fill="#febc2e" fill-opacity=".85"/>
<circle cx="64" cy="22.5" r="6" fill="#28c840" fill-opacity=".85"/>
<text x="{W / 2}" y="27" text-anchor="middle" class="title">{esc(title)}</text>
{body}
</svg>
"""


def prompt(user: str, path: str = "~", delay: float | None = None) -> str:
    anim = "" if delay is None else f' k" style="animation-delay:{delay:.2f}s'
    return (f'<tspan class="u{anim}">{esc(user)}@github</tspan>'
            f'<tspan class="ps{anim}">:{esc(path)}$ </tspan>')


def line(y: float, content: str, cls: str = "", x: float = PAD,
         delay: float | None = None) -> str:
    classes = cls + (" r" if delay is not None else "")
    attrs = f' class="{classes.strip()}"' if classes.strip() else ""
    if delay is not None:
        attrs += f' style="animation-delay:{delay:.2f}s"'
    return f'<text x="{x}" y="{y}" xml:space="preserve"{attrs}>{content}</text>'


def chip_rows(items: list[str], top: float, colors: dict | None = None):
    fs, h, gap = 14, 30, 10
    x, y, out = PAD, top, []
    for name in items:
        has_dot = colors is not None
        w = len(name) * fs * CH + 28 + (16 if has_dot else 0)
        if x + w > W - PAD and x > PAD:
            x, y = PAD, y + h + gap
        out.append(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{h}" rx="7" '
                   f'fill="{THEME["chip"]}" stroke="{THEME["chip_border"]}"/>')
        tx = x + 14
        if has_dot:
            color = colors.get(name, "#8b949e")
            out.append(f'<circle cx="{x + 17:.1f}" cy="{y + h / 2}" r="4.5" fill="{color}"/>')
            tx = x + 30
        out.append(f'<text x="{tx:.1f}" y="{y + h / 2 + 5}" style="font-size:{fs}px">{esc(name)}</text>')
        x += w + gap
    return "\n".join(out), y + h


def ago(iso: str, now: dt.datetime) -> str:
    when = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    days = (now - when).days
    if days < 1:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 30:
        return f"{days} days ago"
    if days < 365:
        m = days // 30
        return f"{m} month{'s' if m > 1 else ''} ago"
    y = days // 365
    return f"{y} year{'s' if y > 1 else ''} ago"


# ------------------------------------------------------------ tarjetas -----
def render_hero(p: dict) -> str:
    user = p["username"]
    step, t = 0.065, 0.6          # velocidad de tipeo y reloj de la animación
    out = []

    def typed(cmd: str, start: float) -> str:
        return "".join(f'<tspan class="k" style="animation-delay:{start + i * step:.2f}s">{esc(c)}</tspan>'
                       for i, c in enumerate(cmd))

    y = BAR + 44
    out.append(line(y, prompt(user) + typed("whoami", t)))
    t += 6 * step + 0.3
    y += 42
    out.append(line(y, esc(p.get("name") or user), "name", delay=t))
    t += 0.15
    if p.get("role"):
        y += 32
        out.append(line(y, esc(p["role"]), "a2", delay=t))
        t += 0.15
    if p.get("availability"):
        y += LH
        out.append(line(y, f'<tspan class="a1">●</tspan> {esc(p["availability"])}', "mut sm", delay=t))
        t += 0.15

    bio = p.get("bio") or p.get("tagline")
    if bio:
        t += 0.4
        y += 46
        out.append(line(y, prompt(user, delay=t) + typed("cat about.txt", t + 0.25)))
        t += 0.25 + 13 * step + 0.3
        width = int((W - 2 * PAD) / (FS * CH)) - 6
        for i, chunk in enumerate(textwrap.wrap(bio, width)):
            y += 34 if i == 0 else LH
            out.append(line(y, esc(chunk), "bio", delay=t))
            t += 0.1

    t += 0.35
    y += 46
    out.append(line(y, prompt(user) + '<tspan class="cur">█</tspan>', delay=t))

    css = f"""
    .name {{ font-size: 26px; font-weight: 700; }}
    .bio {{ fill: {THEME['text']}; fill-opacity: .82; }}
    .cur {{ fill: {p['accent']}; animation: blink 1.1s steps(1) infinite; }}
    .r {{ animation: hide .01s backwards; }}
    .k {{ animation: hidek .01s backwards; }}
    @keyframes hide {{ from, to {{ opacity: 0; }} }}
    @keyframes hidek {{ from, to {{ fill-opacity: 0; }} }}
    @keyframes blink {{ 50% {{ fill-opacity: 0; }} }}
    """
    label = f"{p.get('name') or user}: {p.get('role', '')}. {bio or ''}"
    return window(f"{user}@github: ~ — zsh", label, "\n".join(out), y + 36, p, css)


def render_stack(p: dict, repos: list[dict]) -> str:
    user = p["username"]
    hidden = set(p["hide_languages"])
    counts = Counter(r["language"] for r in repos
                     if r["language"] and r["language"] not in hidden)
    languages = [lang for lang, _ in counts.most_common()]
    out, y = [], BAR + 44
    if languages:
        out.append(line(y, prompt(user) + "ls ~/stack/languages"))
        chips, bottom = chip_rows(languages, y + 16, LANG_COLORS)
        out.append(chips)
        y = bottom + 46
    if p["skills"]:
        out.append(line(y, prompt(user) + "ls ~/stack/tools"))
        chips, bottom = chip_rows(p["skills"], y + 16)
        out.append(chips)
        y = bottom + 46
    label = "Languages: " + ", ".join(languages) + ". Tools: " + ", ".join(p["skills"])
    return window(f"{user}@github: ~/stack", label, "\n".join(out), y - 46 + 34, p)


def pick_projects(p: dict, repos: list[dict]) -> list[dict]:
    by_name = {r["name"].lower(): r for r in repos}
    chosen = []
    for item in p["projects"]:
        name = item if isinstance(item, str) else item.get("name", "")
        repo = dict(by_name.get(name.lower(), {"name": name, "language": None, "stars": 0,
                                                "pushed_at": None, "description": ""}))
        if isinstance(item, dict) and item.get("description"):
            repo["description"] = item["description"]
        chosen.append(repo)
    if not chosen:
        pool = [r for r in repos if r["name"].lower() != p["username"].lower()]
        pool.sort(key=lambda r: r["pushed_at"] or "", reverse=True)
        pool.sort(key=lambda r: r["stars"], reverse=True)   # orden estable: estrellas, luego recientes
        chosen = pool
    return chosen[: p["projects_limit"]]


def render_projects(p: dict, repos: list[dict], now: dt.datetime) -> str:
    user = p["username"]
    rows = pick_projects(p, repos)
    fs = 14
    cw = fs * CH
    name_chars = min(max([len(r["name"]) for r in rows] + [4]), 30)
    x_name = PAD
    x_lang = x_name + (name_chars + 3) * cw
    x_desc = x_lang + 14 * cw
    x_upd = W - PAD                       # alineado a la derecha
    x_star = x_upd - 15 * cw              # alineado a la derecha
    desc_chars = int((x_star - 6 * cw - x_desc) / cw)
    # la columna de descripción solo aparece si al menos la mitad de los repos tiene una
    any_desc = sum(bool(r["description"]) for r in rows) * 2 >= max(len(rows), 1)

    out, y = [], BAR + 44
    out.append(line(y, prompt(user) + f"gh repo list --source --limit {len(rows)}"))
    y += 38
    head = [(x_name, "NAME", "start"), (x_lang, "LANGUAGE", "start"),
            (x_star, "★", "end"), (x_upd, "UPDATED", "end")]
    if any_desc:
        head.insert(2, (x_desc, "DESCRIPTION", "start"))
    for x, label, anchor in head:
        out.append(f'<text x="{x:.1f}" y="{y}" class="dim xs" text-anchor="{anchor}">{label}</text>')
    for r in rows:
        y += 30
        out.append(f'<text x="{x_name}" y="{y}" class="a2" style="font-size:{fs}px">{esc(clip(r["name"], name_chars))}</text>')
        if r["language"]:
            color = LANG_COLORS.get(r["language"], "#8b949e")
            out.append(f'<circle cx="{x_lang + 4.5:.1f}" cy="{y - 4.5}" r="4.5" fill="{color}"/>')
            out.append(f'<text x="{x_lang + 16:.1f}" y="{y}" class="mut" style="font-size:{fs}px">{esc(r["language"])}</text>')
        if any_desc and r["description"]:
            out.append(f'<text x="{x_desc:.1f}" y="{y}" class="dim" style="font-size:{fs}px">{esc(clip(r["description"], desc_chars))}</text>')
        out.append(f'<text x="{x_star:.1f}" y="{y}" class="mut" text-anchor="end" style="font-size:{fs}px">{r["stars"]}</text>')
        updated = ago(r["pushed_at"], now) if r["pushed_at"] else ""
        out.append(f'<text x="{x_upd}" y="{y}" class="mut" text-anchor="end" style="font-size:{fs}px">{updated}</text>')
    label = "Projects: " + ", ".join(r["name"] for r in rows)
    return window(f"{user}@github: ~/projects", label, "\n".join(out), y + 34, p)


def render_activity(p: dict, cal: dict, now: dt.datetime) -> str:
    user = p["username"]
    days = sorted((dt.date.fromisoformat(d), lvl) for d, lvl in cal["days"])
    first = days[0][0]
    sunday = first - dt.timedelta(days=(first.weekday() + 1) % 7)
    cell, stepx = 11, 14
    gx = PAD + 34

    out, y = [], BAR + 44
    out.append(line(y, prompt(user) + 'git log --oneline --since="1 year ago" | wc -l'))
    y += 32
    out.append(line(y, f'<tspan class="a1" style="font-weight:700">{cal["total"]:,}</tspan>'
                       f'<tspan class="mut"> contributions in the last year</tspan>'))
    y += 36
    gy = y + 10

    # etiquetas de mes: donde cambia el mes de la primera fecha de cada columna
    last_col, last_month = -9, None
    cols = {}
    for d, _ in days:
        cols.setdefault((d - sunday).days // 7, d)
    for c in sorted(cols):
        m = cols[c].month
        if m != last_month and c - last_col >= 3:
            out.append(f'<text x="{gx + c * stepx}" y="{y}" class="mut xs">{cols[c].strftime("%b")}</text>')
            last_col = c
        last_month = m

    for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        out.append(f'<text x="{PAD}" y="{gy + row * stepx + 9}" class="dim xs">{name}</text>')

    shade = {0: None, 1: .3, 2: .52, 3: .76, 4: 1}
    for d, lvl in days:
        c, r = (d - sunday).days // 7, (d.weekday() + 1) % 7
        x, yy = gx + c * stepx, gy + r * stepx
        if shade[lvl] is None:
            out.append(f'<rect x="{x}" y="{yy}" width="{cell}" height="{cell}" rx="2" fill="{THEME["empty"]}"/>')
        else:
            out.append(f'<rect x="{x}" y="{yy}" width="{cell}" height="{cell}" rx="2" '
                       f'fill="{p["accent"]}" fill-opacity="{shade[lvl]}"><title>{d.isoformat()}</title></rect>')

    y = gy + 7 * stepx + 26
    out.append(f'<text x="{PAD}" y="{y}" class="dim xs">updated {now.strftime("%b %d, %Y")}</text>')
    lx = W - PAD - 30
    out.append(f'<text x="{lx + 30}" y="{y}" class="dim xs" text-anchor="end">more</text>')
    for i in range(4, -1, -1):
        lx -= stepx
        fill = (f'fill="{THEME["empty"]}"' if i == 0
                else f'fill="{p["accent"]}" fill-opacity="{shade[i]}"')
        out.append(f'<rect x="{lx}" y="{y - 10}" width="{cell}" height="{cell}" rx="2" {fill}/>')
    out.append(f'<text x="{lx - 8}" y="{y}" class="dim xs" text-anchor="end">less</text>')

    label = f"{cal['total']} contributions in the last year"
    return window(f"{user}@github: ~/activity", label, "\n".join(out), y + 24, p)


# ---------------------------------------------------------------- main -----
def write(name: str, svg: str) -> None:
    with open(os.path.join(ASSETS, name), "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"  ✓ assets/{name}")


def main() -> None:
    p = load_profile()
    user = p["username"]
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    now = dt.datetime.now(dt.timezone.utc)
    os.makedirs(ASSETS, exist_ok=True)
    print(f"Generando tarjetas para @{user}")

    if not (p.get("name") and p.get("bio")):
        try:
            gh = http(f"{API}/users/{user}", token)
            p.setdefault("name", gh.get("name"))
            if not p.get("bio"):
                p["bio"] = gh.get("bio") or ""
        except Exception as e:  # noqa: BLE001
            print(f"  ! no pude leer el perfil ({e}); uso solo profile.json")

    write("hero.svg", render_hero(p))

    try:
        repos = fetch_repos(user, token)
        write("stack.svg", render_stack(p, repos))
        write("projects.svg", render_projects(p, repos, now))
    except Exception as e:  # noqa: BLE001
        print(f"  ! no pude leer los repos ({e}); conservo stack.svg y projects.svg anteriores")

    try:
        write("activity.svg", render_activity(p, fetch_calendar(user, token), now))
    except Exception as e:  # noqa: BLE001
        print(f"  ! no pude leer las contribuciones ({e}); conservo activity.svg anterior")


if __name__ == "__main__":
    main()
