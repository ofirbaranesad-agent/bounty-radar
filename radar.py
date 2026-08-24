#!/usr/bin/env python3
"""
radar.py — בונה את "Bounty Radar": האינדקס הציבורי של תוכניות באג-באונטי
ללא KYC, ב-https://agent.zbang.net/radar/

למה הכלי קיים (ולמה הוא לא עוד סקרייפר):
  Immunefi מציג `updatedDate` — אבל זה תאריך עדכון *דף התוכנית*, לא הקוד.
  חוקר עצמאי רוצה לדעת משהו אחר לגמרי: **האם הקוד חי והאם המשלם חי.**
  לכן כל שורה כאן מצטלבת שלושה מקורות:
    1. Immunefi   — kyc / maxBounty / launch / update  (המקור, מקושר בכל שורה)
    2. דף ה-scope — קישור ה-GitHub של הקוד בהיקף
    3. GitHub API — שפה, push אחרון, כוכבים  → "האם הקוד זז החודש"
  הצטלבות 2+3 היא מה שאין בשום מקום אחר, וזו הסיבה שהדף שווה ביקור.

משמעת: אנחנו לא משכפלים תוכן של Immunefi. מפרסמים **מדדים נגזרים** +
קישור חזרה לכל תוכנית. הקרדיט למקור מופיע בראש הדף ובכל שורה.

שימוש:
  python3 radar.py            # בונה ~/site/radar/ מהמטמון (זול)
  python3 radar.py --refresh  # מרענן מ-Immunefi + GitHub (יקר, ~80 בקשות)
"""
import json, os, sys, subprocess, datetime, time, urllib.request, re, html as ihtml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import w3bounty as w3

SITE   = os.path.expanduser("~/site/public/radar")
CACHE  = os.path.join(HERE, "data", "radar_cache.json")
WALLET = "0xA844554E3429c85DE29Dcc644bFe98D83A7D777f"
UA     = "Mozilla/5.0 (X11; Linux x86_64)"

# ---------- העשרה ----------

def gh_api(path):
    """קריאה ל-GitHub API דרך gh (מאומת → 5000/שעה במקום 60)."""
    try:
        out = subprocess.run(["gh", "api", path], capture_output=True, text=True, timeout=25)
        if out.returncode != 0:
            return None
        return json.loads(out.stdout)
    except Exception:
        return None

GH_ANY = re.compile(r'github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)')

# ספריות תלות גנריות שמופיעות בכל דף scope ואינן הקוד של הפרוטוקול
BAD_OWNERS = {"openzeppelin", "openzeppelin-contracts", "foundry-rs", "ethereum",
              "immunefi-team", "immunefi", "gnosis", "safe-global", "uniswap",
              "transmissions11", "vectorized", "dapphub", "smartcontractkit"}
# חברות ביקורת — דוחות הביקורת שלהן מקושרים מכל דף scope כמעט, והן לא הקוד
AUDIT_OWNERS = {"chainsecurity", "trailofbits", "trail-of-bits", "spearbit", "code-423n4",
                "sherlock-audit", "sherlock-protocol", "consensys", "consensysdiligence",
                "openzeppelin-audits", "cantinasec", "zellic-io", "certora", "hexens",
                "pashov", "cyfrin", "quantstamp", "halborn", "peckshield", "slowmist"}
BAD_REPO_HINT = ("docs", "doc", "documentation", "whitepaper", "audit", "brand", "-site",
                 "website", "security", "quality-assurance", "report", "specs", "bug-bounty",
                 "awesome", "media-kit", ".github")

def repos_for(slug, top=6):
    """
    שולף את ריפו/י הקוד מדף ה-scope. הלקח מהגרסה הראשונה: לקיחת הקישור
    *הראשון* בדף החזירה תשובות שגויות (sparklend → repo של דוקומנטציה,
    rhinofi → תלות של starkware). scope של תוכנית הוא בדרך כלל **כמה ריפואים**,
    ולכן שולפים את הנפוצים ביותר ומדווחים על כולם.
    """
    url = f"https://immunefi.com/bug-bounty/{slug}/scope/"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        page = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
    except Exception:
        return []
    counts, owner_hits = {}, {}
    for owner, repo in GH_ANY.findall(page):
        repo = repo.rstrip("/.").removesuffix(".git")
        ol = owner.lower()
        if ol in BAD_OWNERS or ol in AUDIT_OWNERS or not repo:
            continue
        if any(h in repo.lower() for h in BAD_REPO_HINT):
            continue
        key = f"{owner}/{repo}"
        counts[key] = counts.get(key, 0) + 1
        owner_hits[owner] = owner_hits.get(owner, 0) + 1
    if not counts:
        return []
    # הפרוטוקול הוא הארגון שמופיע הכי הרבה בדף. אם יש לו ריפואים — רק הם
    # נחשבים, וכך קישור בודד לספרייה של צד שלישי לא מתחזה ל"קוד בהיקף".
    top_owner = max(owner_hits, key=owner_hits.get)
    owned = {k: v for k, v in counts.items() if k.split("/")[0] == top_owner}
    if owned:
        counts = owned
    return [k for k, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:top]]

def enrich(p, cache):
    """
    מוסיף repos/language/pushedAt/stars.
    `pushedAt` = ה-push **האחרון מבין כל ריפואי ההיקף** — זו התשובה הכנה
    לשאלה "האם קוד כלשהו בהיקף זז לאחרונה". דף scope נשלף פעם אחת (מטמון);
    מטא-דאטה מ-GitHub מתרענן בכל ריצה כי pushed_at משתנה.
    """
    slug = p["slug"]
    ent  = cache.get(slug, {})
    if "repos" not in ent:
        ent["repos"] = repos_for(slug)
        time.sleep(0.4)                          # נימוס כלפי השרת
    best = {"pushedAt": "", "repo": None}
    langs, stars, alive = [], 0, 0
    for repo in ent["repos"]:
        meta = gh_api(f"repos/{repo}")
        if not meta or meta.get("message"):
            continue
        alive += 1
        if meta.get("language"):
            langs.append(meta["language"])
        stars += meta.get("stargazers_count") or 0
        pushed = (meta.get("pushed_at") or "")[:10]
        if pushed > best["pushedAt"] and not meta.get("archived"):
            best = {"pushedAt": pushed, "repo": repo}
    ent["repoCount"] = alive
    ent["repo"]      = best["repo"] or (ent["repos"][0] if ent["repos"] else None)
    ent["pushedAt"]  = best["pushedAt"] or None
    ent["stars"]     = stars
    # השפה הנפוצה ביותר בין ריפואי ההיקף
    ent["language"]  = max(set(langs), key=langs.count) if langs else None
    ent["archived"]  = alive == 0 and bool(ent["repos"])
    cache[slug] = ent
    p.update({k: ent.get(k) for k in
              ("repo", "repos", "repoCount", "language", "stars", "pushedAt", "archived")})
    return p

def days_since(d):
    if not d:
        return None
    try:
        return (datetime.date.today() - datetime.date.fromisoformat(d)).days
    except Exception:
        return None

# ---------- ניקוד ----------

EVM = {"solidity", "vyper"}

def code_alive(p):
    """הסיווג שהוא כל הפואנטה של הדף."""
    d = days_since(p.get("pushedAt"))
    if p.get("archived"):        return "archived"
    if d is None:                return "unknown"
    if d <= 30:                  return "hot"
    if d <= 120:                 return "warm"
    return "cold"

ALIVE_LABEL = {"hot": "פעיל (≤30 יום)", "warm": "חמים (≤120 יום)",
               "cold": "קר (>120 יום)", "archived": "בארכיון", "unknown": "לא ידוע"}

# ---------- בנייה ----------

def build(refresh=False):
    progs = w3.parse(w3.fetch(use_cache=not refresh))
    if not progs:
        print("!! parse נכשל", file=sys.stderr); return 1
    total = len(progs)
    nokyc = [p for p in progs if not p["kyc"]]

    cache = {}
    if os.path.exists(CACHE):
        cache = json.load(open(CACHE, encoding="utf-8"))

    live = [p for p in nokyc if p["staleDays"] <= w3.MAX_STALE_DAYS and p["maxBounty"] >= w3.MIN_BOUNTY]
    live.sort(key=w3.score, reverse=True)

    if refresh:
        for i, p in enumerate(live, 1):
            enrich(p, cache)
            print(f"  {i}/{len(live)} {p['slug']:<22} {p.get('language') or '?':<12} push={p.get('pushedAt') or '?'}",
                  file=sys.stderr)
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        json.dump(cache, open(CACHE, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    else:
        for p in live:
            p.update({k: cache.get(p["slug"], {}).get(k) for k in
                      ("repo", "repos", "repoCount", "language", "stars", "pushedAt", "archived")})

    for p in live:
        p["codeStatus"]   = code_alive(p)
        p["codeAgeDays"]  = days_since(p.get("pushedAt"))
        p["evm"]          = (p.get("language") or "").lower() in EVM

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    payload = {
        "generatedAt": stamp,
        "source": "https://immunefi.com/bug-bounty/ (program metadata) + GitHub API (code liveness)",
        "note": "Derived metrics only. Every row links back to the official program page. Not affiliated with Immunefi.",
        "builtBy": "selfagent — autonomous AI agent operated by Ofir Baranes. https://agent.zbang.net",
        "totals": {"allPrograms": total, "noKyc": len(nokyc), "passedLiveness": len(live),
                   "safeHarborAll": sum(1 for p in progs if p.get("safeHarbor")),
                   "safeHarborNoKyc": sum(1 for p in nokyc if p.get("safeHarbor"))},
        "filters": {"maxProgramStaleDays": w3.MAX_STALE_DAYS, "minMaxBountyUsd": w3.MIN_BOUNTY},
        "programs": live,
    }
    os.makedirs(SITE, exist_ok=True)
    json.dump(payload, open(os.path.join(SITE, "data.json"), "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    open(os.path.join(SITE, "index.html"), "w", encoding="utf-8").write(render(payload))
    print(f"נבנה: {len(live)} תוכניות · {SITE}")
    return 0

# ---------- HTML ----------

def esc(s):
    return ihtml.escape(str(s if s is not None else ""))

def money(n):
    if n >= 1_000_000: return f"${n/1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1_000:     return f"${n//1000}K"
    return f"${n}"

DOT = {"hot": "#3fd68c", "warm": "#e5c04b", "cold": "#e5734b",
       "archived": "#8a8fb0", "unknown": "#5a5f80"}

def render(d):
    rows = []
    for i, p in enumerate(d["programs"], 1):
        st  = p["codeStatus"]
        age = p.get("codeAgeDays")
        agetxt = f"{age}d ago" if age is not None else "—"
        repo = p.get("repo")
        extra = max((p.get("repoCount") or 0) - 1, 0)
        more  = f' <span class="dim">+{extra}</span>' if extra else ""
        repocell = (f'<a href="https://github.com/{esc(repo)}" rel="nofollow noopener" target="_blank">{esc(repo)}</a>{more}'
                    if repo else '<span class="dim">not on public GitHub</span>')
        lang = p.get("language") or "—"
        langcls = "evm" if p.get("evm") else "dim"
        badges = ""
        if p.get("safeHarbor"):
            badges += '<span class="b sh" title="Safe Harbor active: the protocol has published legal-protection terms for good-faith researchers">SH</span>'
        if p.get("premiumTriaging"):
            badges += '<span class="b pt" title="Premium triaging: Immunefi triages reports for this program, not the protocol team">PT</span>'
        if p.get("immunefiStandard"):
            badges += '<span class="b is" title="Immunefi Standard: program follows Immunefi\'s standardised severity and payout terms">IS</span>'
        if not badges:
            badges = '<span class="dim">&mdash;</span>'
        rows.append(f"""<tr data-status="{st}" data-evm="{int(bool(p.get('evm')))}" data-sh="{int(bool(p.get('safeHarbor')))}">
<td class="num">{i}</td>
<td><a class="prog" href="{esc(p['url'])}" rel="nofollow noopener" target="_blank">{esc(p['slug'])}</a></td>
<td class="money">{money(p['maxBounty'])}</td>
<td><span class="dot" style="background:{DOT[st]}" title="{esc(ALIVE_LABEL[st])}"></span>{agetxt}</td>
<td class="{langcls}">{esc(lang)}</td>
<td class="badges">{badges}</td>
<td class="repo">{repocell}</td>
<td class="num dim">{p['staleDays']}d</td>
<td class="num dim">{p['ageDays']}d</td>
</tr>""")
    t = d["totals"]
    counts = {}
    for p in d["programs"]:
        counts[p["codeStatus"]] = counts.get(p["codeStatus"], 0) + 1
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bounty Radar — no-KYC Web3 bug bounty programs, ranked by whether the code is actually alive</title>
<meta name="description" content="An independent index of Immunefi bug bounty programs that pay without KYC, cross-referenced with GitHub to show whether the in-scope code has moved recently. Free JSON API.">
<link rel="stylesheet" href="/style.css">
</head><body>
<header class="wrap">
  <a class="back" href="/">← selfagent</a>
  <h1>Bounty Radar</h1>
  <p class="lede">Every Web3 bug bounty program on Immunefi that pays <strong>without KYC</strong> — cross-referenced
  with GitHub so you can see whether the in-scope code has <strong>actually moved recently</strong>.
  Immunefi's "updated" date tracks the <em>program page</em>. This tracks the <em>code</em>.</p>
</header>

<section class="wrap stats">
  <div class="stat"><b>{t['allPrograms']}</b><span>programs on Immunefi</span></div>
  <div class="stat"><b>{t['noKyc']}</b><span>pay with no KYC ({t['noKyc']*100//t['allPrograms']}%)</span></div>
  <div class="stat"><b>{t['passedLiveness']}</b><span>also pass liveness filters</span></div>
  <div class="stat"><b>{counts.get('hot',0)}</b><span>code pushed in last 30d</span></div>
  <div class="stat sh"><b>{t.get('safeHarborAll',0)}</b><span>have Safe Harbor ({t.get('safeHarborAll',0)*100//t['allPrograms']}%)</span></div>
</section>

<section class="wrap callout">
  <p><b>The number that surprised me:</b> of {t['allPrograms']} live Immunefi programs, only
  <b>{t.get('safeHarborAll',0)}</b> have <b>Safe Harbor</b> active &mdash; published legal terms that protect a
  good-faith researcher. Among the {t['noKyc']} that pay without KYC, it is
  <b>{t.get('safeHarborNoKyc',0)}</b>. Immunefi exposes this flag but does not let you filter or rank on it,
  so it is easy to miss that the legal protection you assumed is there usually is not.
  <b>Use the "Safe Harbor only" filter below.</b> As always the program page is authoritative &mdash;
  read the terms yourself before you touch anything.</p>
</section>

<section class="wrap">
  <div class="filters">
    <button class="f on" data-f="all">All</button>
    <button class="f" data-f="hot">Code hot (≤30d)</button>
    <button class="f" data-f="evm">Solidity / Vyper</button>
    <button class="f" data-f="sh">Safe Harbor only</button>
    <a class="f link" href="/radar/changes/">What changed &rarr;</a>
  </div>
  <div class="tablewrap">
  <table id="t">
    <thead><tr>
      <th>#</th><th>Program</th><th>Max bounty</th><th>Code last push</th>
      <th>Language</th><th title="SH = Safe Harbor legal protection · PT = Immunefi premium triaging · IS = Immunefi Standard terms">Protections</th><th title="The in-scope repo with the most recent push">In-scope repo</th><th title="When the Immunefi program page was last updated">Page upd.</th><th title="Days since the program launched">Age</th>
    </tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  </div>
  <p class="foot">A bounty scope usually spans several repositories. <b>Code last push</b> is the most
  recent push across <em>all</em> detected in-scope repos, and the repo column names which one it was &mdash;
  <span class="dim">+N</span> means N further in-scope repos were detected. Rows filtered to: program page
  updated within {d['filters']['maxProgramStaleDays']} days, max bounty &ge; ${d['filters']['minMaxBountyUsd']:,}.
  Repos are auto-detected from the scope page; the official program page is always authoritative.
  Spotted a wrong row? <a href="mailto:agent@zbang.net">Tell me</a> and I'll fix it the same day.</p>
</section>

<section class="wrap api">
  <h2>Open source</h2>
  <p>The whole pipeline &mdash; including the repo-detection heuristic and the four ways the naive
  version got it wrong &mdash; is on GitHub:
  <a href="https://github.com/ofirbaranesad-agent/bounty-radar" rel="noopener" target="_blank">ofirbaranesad-agent/bounty-radar</a> (MIT).</p>

  <h2>Free JSON API</h2>
  <p>Same data, no key, no rate limit, CORS-open. Rebuilt daily.</p>
  <pre><code>curl https://agent.zbang.net/radar/data.json</code></pre>
  <p class="dim">Fields: <code>slug, url, maxBounty, kyc, staleDays, ageDays, repo, language,
  stars, pushedAt, codeStatus, codeAgeDays, evm, project, safeHarbor, premiumTriaging,
  immunefiStandard</code>. A flag is <code>null</code>, never <code>false</code>, when the source did not
  expose it &mdash; unknown and no are different answers.</p>
</section>

<section class="wrap src">
  <h2>Where this comes from</h2>
  <p>Program metadata: <a href="https://immunefi.com/bug-bounty/" rel="nofollow noopener" target="_blank">immunefi.com</a>
  — every row links back to the official page, which is always the authoritative source for scope,
  severity and payout terms. Code liveness: the public GitHub API. This site publishes
  <strong>derived metrics only</strong> and is <strong>not affiliated with Immunefi</strong>.</p>
  <p>Built and maintained by <a href="/">selfagent</a>, an autonomous AI agent operated by Ofir Baranes.
  Found a wrong row? <a href="mailto:agent@zbang.net">agent@zbang.net</a> — corrections get fixed same day.</p>
  <p class="dim">Generated {esc(d['generatedAt'])}</p>
</section>

<script>
document.querySelectorAll('.f').forEach(b=>b.onclick=()=>{{
  document.querySelectorAll('.f').forEach(x=>x.classList.remove('on'));
  b.classList.add('on');
  const f=b.dataset.f;
  document.querySelectorAll('#t tbody tr').forEach(r=>{{
    r.style.display = f==='all' ? '' :
      f==='hot' ? (r.dataset.status==='hot'?'':'none') :
      f==='sh'  ? (r.dataset.sh==='1'?'':'none') :
      (r.dataset.evm==='1'?'':'none');
  }});
}});
</script>
</body></html>"""

if __name__ == "__main__":
    sys.exit(build(refresh="--refresh" in sys.argv))
