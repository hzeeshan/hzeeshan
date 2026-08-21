#!/usr/bin/env python3
"""Build the profile card SVGs (dark + light): halftone portrait + neofetch panel."""
import json, math, os, sys, urllib.request
from PIL import Image, ImageOps, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHOTO = os.path.join(ROOT, "assets", "profile.jpg")
CROP = (250, 10, 570, 400)

# ---------- stats ----------
def fetch_stats():
    token = os.environ.get("GH_TOKEN")
    cache = os.path.join(ROOT, "assets", "stats.json")
    if token:
        q = """query($login:String!){ user(login:$login){
            followers{totalCount}
            repositories(ownerAffiliations:OWNER, first:100){totalCount nodes{stargazerCount isFork}}
            contributionsCollection{totalCommitContributions restrictedContributionsCount}}}"""
        req = urllib.request.Request(
            "https://api.github.com/graphql",
            data=json.dumps({"query": q, "variables": {"login": "hzeeshan"}}).encode(),
            headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.load(r)["data"]["user"]
            repos = d["repositories"]
            c = d["contributionsCollection"]
            stats = {
                "repos": repos["totalCount"],
                "forks": sum(1 for n in repos["nodes"] if n["isFork"]),
                "stars": sum(n["stargazerCount"] for n in repos["nodes"]),
                "contribs": c["totalCommitContributions"] + c["restrictedContributionsCount"],
                "followers": d["followers"]["totalCount"],
            }
            json.dump(stats, open(cache, "w"))
            return stats
        except Exception as e:
            print(f"stats fetch failed ({e}), using cache", file=sys.stderr)
    return json.load(open(cache))

# ---------- halftone ----------
def halftone_dots(cols=56, cell=6.0):
    from collections import deque
    img = Image.open(PHOTO).convert("L").crop(CROP)
    img = img.filter(ImageFilter.MedianFilter(3))
    img = ImageOps.autocontrast(img, cutoff=1)
    px = img.load(); w, h = img.size
    sat = Image.open(PHOTO).convert("HSV").crop(CROP).split()[1].load()
    # background mask: bright, unsaturated pixels connected to the image border
    isbg_px = [[False]*w for _ in range(h)]
    cand = [[px[x, y] > 200 and sat[x, y] < 50 for x in range(w)] for y in range(h)]
    dq = deque()
    for x in range(w):
        for y in (0, h-1):
            if cand[y][x] and not isbg_px[y][x]:
                isbg_px[y][x] = True; dq.append((x, y))
    for y in range(h):
        for x in (0, w-1):
            if cand[y][x] and not isbg_px[y][x]:
                isbg_px[y][x] = True; dq.append((x, y))
    while dq:
        x, y = dq.popleft()
        for nx, ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
            if 0 <= nx < w and 0 <= ny < h and cand[ny][nx] and not isbg_px[ny][nx]:
                isbg_px[ny][nx] = True; dq.append((nx, ny))
    # solidify hair band: everything on the subject side goes dark
    bh = int(h * 0.17)
    for y in range(bh):
        for x in range(w):
            if not isbg_px[y][x]:
                px[x, y] = min(px[x, y], 60)
    # lift the hairline shadow: below the band, non-hair pixels brighten so
    # forehead skin starts right at the real hair boundary
    for y in range(bh, int(h * 0.36)):
        for x in range(w):
            if not isbg_px[y][x] and px[x, y] > 80:
                px[x, y] = min(255, int(px[x, y] * 1.9))
    rows = int(cols * (h / w))
    small = img.resize((cols, rows), Image.LANCZOS)
    sp = small.load()
    # downsample bg mask (majority)
    cw_f, ch_f = w / cols, h / rows
    dots = []   # (cx, cy, darkness 0..1, is_background)
    for y in range(rows):
        for x in range(cols):
            xs, ys = int(x * cw_f), int(y * ch_f)
            n = bg = 0
            for yy in range(ys, min(int(ys + ch_f) + 1, h), 2):
                for xx in range(xs, min(int(xs + cw_f) + 1, w), 2):
                    n += 1; bg += isbg_px[yy][xx]
            v = 1 - sp[x, y] / 255
            dots.append((x * cell + cell/2, y * cell + cell/2, v, bg > n * 0.5))
    return dots, cols * cell, rows * cell

# ---------- svg ----------
def dot_leader(label, value, width=58):
    n = width - len(label) - len(value)
    return label, "." * max(n, 2), value

def build(theme, stats):
    dark = theme == "dark"
    BG      = "#0d1117" if dark else "#ffffff"
    CARD    = "#161b22" if dark else "#f6f8fa"
    BORDER  = "#30363d" if dark else "#d0d7de"
    FG      = "#e6edf3" if dark else "#1f2328"
    MUTED   = "#8b949e" if dark else "#57606a"
    ACCENT  = "#58a6ff" if dark else "#0969da"
    GREEN   = "#3fb950" if dark else "#1a7f37"
    DOT     = "#e6edf3" if dark else "#24292f"

    dots, pw, ph = halftone_dots()
    P_X, P_Y = 36, 40
    scale = 300 / pw
    r_max = 3.1

    # dark theme: positive image (draw where photo is light); background dropped.
    # subject pixels keep a faint floor so the silhouette stays visible.
    circles = []
    for cx, cy, v, isbg in dots:
        if isbg:
            continue
        strength = max(1 - v, 0.10) if dark else v ** 1.8
        r = r_max * math.sqrt(strength) * scale
        if r < 0.5:
            continue
        circles.append(f'<circle cx="{P_X + cx*scale:.1f}" cy="{P_Y + cy*scale:.1f}" r="{r:.2f}"/>')

    port_h = ph * scale

    rows = [
        ("t", "hafiz@dev", None, None),
        ("kv", ". OS:", "macOS, Ubuntu, Docker", None),
        ("kv", ". Uptime:", "10 years, 3 months on GitHub", None),
        ("kv", ". Host:", "Freelancer, Torino, Italy", None),
        ("kv", ". Kernel:", "Full Stack Web Developer", None),
        ("kv", ". IDE:", "VS Code, Cursor, Claude Code", None),
        ("gap",) * 1,
        ("kv", ". Languages.Programming:", "PHP, JavaScript, Python", None),
        ("kv", ". Languages.Computer:", "HTML, CSS, SQL, JSON, YAML", None),
        ("kv", ". Languages.Real:", "English, Italian, Urdu", None),
        ("gap",),
        ("kv", ". Stack.Backend:", "Laravel, Filament, NativePHP, MySQL", None),
        ("kv", ". Stack.Frontend:", "Vue.js, Livewire, Tailwind CSS", None),
        ("kv", ". Stack.DevOps:", "Git, Docker, LAMP", None),
        ("gap",),
        ("kv", ". Projects.Portfolio:", "hafiz.dev", ACCENT),
        ("kv", ". Projects.Recent:", "watch-later, forcedbreak", None),
        ("gap",),
        ("t", "- Contact", None, None),
        ("kv", ". Email:", "hafizzeeshan619@gmail.com", None),
        ("kv", ". Portfolio:", "https://hafiz.dev", ACCENT),
        ("kv", ". LinkedIn:", "hafiz-riaz-777501150", None),
        ("gap",),
        ("t", "- GitHub Stats", None, None),
        ("kv", ". Repos:", f"{stats['repos']} {{Forks: {stats['forks']}}}  |  Stars: {stats['stars']}", GREEN),
        ("kv", ". Contributions:", f"{stats['contribs']:,} (last year)  |  Followers: {stats['followers']}", GREEN),
    ]

    T_X, line_h, fs = 372, 19.5, 12.6
    CHW = fs * 0.602                     # monospace char width
    PANEL_CHARS = 62
    y = 52
    texts = []
    mono = "ui-monospace,SFMono-Regular,SF Mono,Menlo,Consolas,monospace"
    for row in rows:
        if row[0] == "gap":
            y += line_h * 0.55
            continue
        def seg(col, s, color, bold=False):
            b = ' font-weight="bold"' if bold else ""
            return (f'<text x="{T_X + col * CHW:.1f}" y="{y:.0f}" fill="{color}"{b} '
                    f'textLength="{len(s) * CHW:.1f}" lengthAdjust="spacingAndGlyphs">'
                    f'{s.replace("&", "&amp;").replace("<", "&lt;")}</text>')
        if row[0] == "t":
            label = row[1]
            texts.append(seg(0, label, FG, bold=True))
            texts.append(seg(len(label) + 1, "-" * (PANEL_CHARS - len(label) - 1), MUTED))
        else:
            _, label, value, vc = row
            lbl, dotsldr, val = dot_leader(label, value, PANEL_CHARS - 2)
            texts.append(seg(0, lbl, FG))
            texts.append(seg(len(lbl) + 1, dotsldr, MUTED))
            texts.append(seg(len(lbl) + 1 + len(dotsldr) + 1, val, vc or FG))
        y += line_h

    H = max(int(P_Y + port_h + 40), int(y + 20))
    W = 960
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <rect width="{W}" height="{H}" rx="10" fill="{CARD}" stroke="{BORDER}"/>
  <g fill="{DOT}">{''.join(circles)}</g>
  <g font-family="{mono}" font-size="{fs}">{''.join(texts)}</g>
</svg>'''
    return svg

stats = fetch_stats()
for theme in ("dark", "light"):
    out = os.path.join(ROOT, "assets", f"card_{theme}.svg")
    open(out, "w").write(build(theme, stats))
    print(f"wrote {out}")
