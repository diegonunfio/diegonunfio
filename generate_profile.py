#!/usr/bin/env python3
import argparse, base64, html, json, os, random, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
CFG = json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))

BG = "#0d1117"
PANEL = "#11161d"
BORDER = "#30363d"
TEXT = "#e6edf3"
MUTED = "#8b9bb4"
GREEN = CFG.get("accent", "#33e37b")
BLUE = CFG.get("accent2", "#4fa3ff")
RED = "#ff5f56"
YELLOW = "#ffbd2e"
DOTGREEN = "#27c93f"

def esc(v):
    return html.escape(str(v), quote=True)

def write_svg(name, body, w=1000, h=260):
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<style>
  .sans {{ font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; }}
  .mono {{ font-family: ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono","Courier New",monospace; }}
  .title {{ fill:{TEXT}; font-weight:700; }}
  .text {{ fill:{TEXT}; }}
  .muted {{ fill:{MUTED}; }}
  .green {{ fill:{GREEN}; }}
  .blue {{ fill:{BLUE}; }}
</style>
<rect width="100%" height="100%" rx="18" fill="{BG}"/>
{body}
</svg>'''
    (ASSETS / name).write_text(svg, encoding="utf-8")

def window(x, y, w, h, command):
    return f'''
<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="#0b0f14" stroke="{BORDER}"/>
<rect x="{x}" y="{y}" width="{w}" height="42" rx="9" fill="{PANEL}" stroke="{BORDER}"/>
<rect x="{x}" y="{y+33}" width="{w}" height="9" fill="{PANEL}"/>
<circle cx="{x+24}" cy="{y+21}" r="7" fill="{RED}"/>
<circle cx="{x+46}" cy="{y+21}" r="7" fill="{YELLOW}"/>
<circle cx="{x+68}" cy="{y+21}" r="7" fill="{DOTGREEN}"/>
<text x="{x+w/2}" y="{y+26}" text-anchor="middle" class="mono muted" font-size="13">{esc(CFG["username"])}@github: ~{esc(command)}</text>
'''

def pill(x, y, label, green=False):
    width = 18 + max(48, len(label) * 8.2)
    stroke = GREEN if green else "#28527a"
    fill = "#10241f" if green else "#101e2d"
    color = "#7fffc1" if green else "#8fc5ff"
    return (
        f'<rect x="{x}" y="{y}" width="{width}" height="30" rx="15" fill="{fill}" stroke="{stroke}"/>'
        f'<text x="{x+width/2}" y="{y+20}" text-anchor="middle" class="sans" font-size="13" '
        f'font-weight="700" fill="{color}">{esc(label)}</text>'
    ), width

def graphql():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return None
    query = r'''
query($login:String!) {
  user(login:$login) {
    login
    name
    avatarUrl(size:160)
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
            date
          }
        }
      }
    }
  }
}
'''
    payload = json.dumps({"query": query, "variables": {"login": CFG["username"]}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-readme-generator"
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["data"]["user"]

def avatar_data(url):
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent":"profile-readme-generator"})
        with urllib.request.urlopen(req, timeout=20) as r:
            ctype = r.headers.get_content_type()
            data = base64.b64encode(r.read()).decode()
            return f"data:{ctype};base64,{data}"
    except Exception:
        return None

def hero(user):
    avatar = avatar_data(user.get("avatarUrl")) if user else None
    username = CFG["username"]
    name = CFG.get("name") or (user or {}).get("name") or username
    role = CFG.get("role", "")
    tagline = CFG.get("tagline", "")
    if avatar:
        portrait = f'''
<defs><clipPath id="avatarClip"><circle cx="78" cy="112" r="43"/></clipPath></defs>
<circle cx="78" cy="112" r="46" fill="#ffffff"/>
<image href="{avatar}" x="35" y="69" width="86" height="86" clip-path="url(#avatarClip)" preserveAspectRatio="xMidYMid slice"/>
'''
    else:
        initials = "".join([p[0] for p in name.split()[:2]]).upper()
        portrait = f'''
<circle cx="78" cy="112" r="46" fill="#ffffff"/>
<circle cx="78" cy="112" r="42" fill="{PANEL}"/>
<text x="78" y="123" text-anchor="middle" class="sans title" font-size="27">{esc(initials)}</text>
'''
    body = f'''
<rect x="26" y="22" width="948" height="44" rx="8" fill="{PANEL}" stroke="{BORDER}"/>
<text x="40" y="49" class="sans blue" font-size="13" font-weight="800">OPEN SOURCE PROFILE</text>
<text x="954" y="49" text-anchor="end" class="sans muted" font-size="13">generated with GitHub Actions</text>
{portrait}
<text x="140" y="103" class="sans green" font-size="12" font-weight="800">LIVE PROFILE</text>
<text x="140" y="132" class="sans title" font-size="30">{esc(username)}</text>
<text x="140" y="157" class="sans muted" font-size="15">{esc(role)}</text>
<text x="140" y="181" class="sans muted" font-size="14">{esc(tagline)}</text>
<line x1="26" y1="203" x2="974" y2="203" stroke="{BORDER}"/>
'''
    write_svg("hero.svg", body, 1000, 224)

def about():
    lines = CFG.get("bio", [])
    body = f'''
<text x="38" y="38" class="sans green" font-size="13" font-weight="800">ABOUT ME</text>
{window(165, 58, 670, 166, " $ cat about.md")}
<text x="188" y="105" class="mono green" font-size="14" font-weight="700">{esc(CFG["username"])}@github</text>
<text x="350" y="105" class="mono text" font-size="14">:~$ cat about.md</text>
'''
    y = 141
    for line in lines:
        body += f'<text x="188" y="{y}" class="mono text" font-size="14">{esc(line)}</text>'
        y += 28
    body += f'<text x="188" y="210" class="mono text" font-size="14">&gt; {esc(CFG.get("availability","open to collaboration"))}</text>'
    write_svg("about.svg", body, 1000, 248)

def skills():
    body = f'''
<text x="38" y="38" class="sans green" font-size="13" font-weight="800">SKILLS</text>
{window(145, 58, 710, 132, " $ ls skills/")}
<text x="168" y="105" class="mono green" font-size="14" font-weight="700">{esc(CFG["username"])}@github</text>
<text x="330" y="105" class="mono text" font-size="14">:~$ ls skills/</text>
'''
    x, y = 168, 127
    for s in CFG.get("skills", []):
        p, width = pill(x, y, s)
        if x + width > 825:
            x = 168
            y += 38
            p, width = pill(x, y, s)
        body += p
        x += width + 10
    write_svg("skills.svg", body, 1000, 220)

def projects():
    projects = CFG.get("projects", [])[:2]
    names = "    ".join(p["name"] for p in projects) or "your-project"
    body = f'''
<text x="38" y="38" class="sans green" font-size="13" font-weight="800">PROJECTS</text>
{window(145, 58, 710, 136, " $ ls -la repos/")}
<text x="168" y="105" class="mono green" font-size="14" font-weight="700">{esc(CFG["username"])}@github</text>
<text x="330" y="105" class="mono text" font-size="14">:~$ ls -la repos/</text>
<text x="168" y="140" class="mono text" font-size="14">{esc(names)}</text>
'''
    card_y = 215
    card_w = 450
    gap = 16
    for i, p in enumerate(projects):
        x = 38 + i*(card_w+gap)
        desc = p.get("description","")
        if len(desc) > 68:
            desc = desc[:65] + "..."
        body += f'''
<rect x="{x}" y="{card_y}" width="{card_w}" height="135" rx="10" fill="{PANEL}" stroke="{BORDER}"/>
<text x="{x+16}" y="{card_y+29}" class="sans title" font-size="16">{esc(p["name"])}</text>
<text x="{x+16}" y="{card_y+58}" class="sans muted" font-size="13">{esc(desc)}</text>
'''
        px = x+16
        for tech in p.get("tech", [])[:4]:
            item, width = pill(px, card_y+82, tech)
            body += item
            px += width + 8
    write_svg("projects.svg", body, 1000, 378)

def offline_calendar():
    random.seed(17)
    weeks = []
    for wi in range(53):
        days = []
        for di in range(7):
            n = 0 if random.random() < .63 else random.choice([1,1,2,3,5,8])
            days.append({"contributionCount": n, "date": f"2026-{(wi%12)+1:02d}-{(di+1):02d}"})
        weeks.append({"contributionDays": days})
    return {
        "totalContributions": sum(d["contributionCount"] for w in weeks for d in w["contributionDays"]),
        "weeks": weeks
    }

def heatmap(user):
    cal = None
    if user:
        cal = user.get("contributionsCollection", {}).get("contributionCalendar")
    if not cal:
        cal = offline_calendar()
    total = cal.get("totalContributions", 0)
    weeks = cal.get("weeks", [])
    body = f'''
<text x="38" y="38" class="sans green" font-size="13" font-weight="800">HEATMAP</text>
{window(145, 58, 710, 196, " $ ./contributions.sh")}
<text x="168" y="105" class="mono green" font-size="14" font-weight="700">{esc(CFG["username"])}@github</text>
<text x="330" y="105" class="mono text" font-size="14">:~$ ./contributions.sh</text>
'''
    x0, y0, s, g = 168, 128, 10, 3
    colors = ["#21262d", "#0e4429", "#006d32", "#26a641", "#39d353"]
    for wi, week in enumerate(weeks[:53]):
        for di, day in enumerate(week.get("contributionDays", [])[:7]):
            c = int(day.get("contributionCount", 0))
            lvl = 0 if c == 0 else 1 if c <= 2 else 2 if c <= 5 else 3 if c <= 9 else 4
            body += f'<rect x="{x0+wi*(s+g)}" y="{y0+di*(s+g)}" width="{s}" height="{s}" rx="2" fill="{colors[lvl]}"/>'
    body += f'<text x="168" y="239" class="mono muted" font-size="13">{total} contributions in the last year</text>'
    write_svg("heatmap.svg", body, 1000, 280)

def focus():
    role = CFG.get("role", "Engineer")
    body = f'''
<text x="38" y="38" class="sans green" font-size="13" font-weight="800">CURRENT FOCUS</text>
<rect x="38" y="62" width="924" height="102" rx="10" fill="{PANEL}" stroke="{BORDER}"/>
<text x="58" y="99" class="sans title" font-size="17">{esc(role)}</text>
<text x="58" y="128" class="sans muted" font-size="14">{esc(CFG.get("tagline",""))}</text>
'''
    write_svg("focus.svg", body, 1000, 190)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    ASSETS.mkdir(exist_ok=True)
    user = None if args.offline else graphql()
    hero(user)
    about()
    skills()
    projects()
    heatmap(user)
    focus()
    print("Generated profile SVGs in", ASSETS)

if __name__ == "__main__":
    main()
