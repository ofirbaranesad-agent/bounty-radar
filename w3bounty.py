#!/usr/bin/env python3
"""
w3bounty.py — סורק תוכניות באג-באונטי Web3 (Immunefi) ומדרג מועמדים.

למה הכלי קיים:
  אפיק ההכנסה היחיד שנמצא (24.8.26) שעוקף גם את חסם ההון (אפס הון נדרש)
  וגם את חסם הזהות המשפטית (תשלום ישיר לארנק, בלי KYC) הוא באג-באונטי
  על תוכניות שמסומנות `kyc:false`.

כלל-העל מ-PLAYBOOK ("אמת עסקה סגורה, לא הצעה מוצגת") מוטמע כאן כשער חיוּת:
  MAX_STALE_DAYS — תוכנית שלא עודכנה לאחרונה = משלם שאולי כבר לא שם.
  זה בדיוק הסינון שהחמצתי ב-Algora ושהרג אפיק שלם.

שימוש:
  python3 w3bounty.py            # דירוג מועמדים (ברירת מחדל: no-KYC בלבד)
  python3 w3bounty.py --all      # כולל תוכניות שדורשות KYC (להשוואה)
  python3 w3bounty.py --json     # פלט גולמי
  python3 w3bounty.py --lang     # מוסיף שפת ה-repo (GitHub) לטופ 25 ומסמן non-Solidity
  python3 w3bounty.py --limit=N  # מציג/מנתח N מועמדים במקום 25 (למשל 26-39 שנותרו)

הלקח מ-24.8.26 (recon של enzyme-onyx): הציון לא בדק שפה בכלל — zest-protocol-v2
עבר את השער בציון 5.41 כשהריפו שלו הוא Clarity (Stacks), לא Solidity/EVM.
--lang סוגר את הפער: שולף את קישור ה-GitHub מדף ה-scope בImmunefi ואת
ה-language מ-GitHub API, רק לטופ 25 (לא לכל 186 — יקר מדי).
"""
import json, re, sys, urllib.request, datetime, os

SRC = "https://immunefi.com/bug-bounty/"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "immunefi.html")
UA = "Mozilla/5.0 (X11; Linux x86_64)"

# --- שערי חיוּת (הלקח מ-Algora, מוטמע בקוד ולא בזיכרון) ---
MAX_STALE_DAYS = 120   # תוכנית שלא עודכנה 120 יום = משלם חשוד
MIN_BOUNTY     = 5000  # מתחת לזה לא שווה את שעות הביקורת

def fetch(use_cache=True):
    if use_cache and os.path.exists(CACHE):
        age = (datetime.datetime.now().timestamp() - os.path.getmtime(CACHE)) / 3600
        if age < 6:
            return open(CACHE, encoding="utf-8", errors="replace").read()
    req = urllib.request.Request(SRC, headers={"User-Agent": UA})
    html = urllib.request.urlopen(req, timeout=45).read().decode("utf-8", "replace")
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    open(CACHE, "w", encoding="utf-8").write(html)
    return html

# הנתונים מוטמעים בדף כ-JSON מוברח בתוך self.__next_f.push — כל גרש מקודם
# בבקסלאש. לכן מבטלים את ההברחה פעם אחת ואז מחפשים JSON רגיל.
REC = re.compile(
    r'"slug":"(?P<slug>[^"]+)","url":"(?P<url>[^"]+)",'
    r'"launchDate":"(?P<launch>[^"]+)","updatedDate":"(?P<updated>[^"]+)",'
    r'"kyc":(?P<kyc>true|false),"maxBounty":(?P<max>\d+)')

def parse(html):
    html = html.replace('\\"', '"')
    out, seen = [], set()
    for m in REC.finditer(html):
        slug = m.group("slug")
        if slug in seen:
            continue
        seen.add(slug)
        upd = datetime.datetime.fromisoformat(m.group("updated").replace("Z", "+00:00"))
        lau = datetime.datetime.fromisoformat(m.group("launch").replace("Z", "+00:00"))
        now = datetime.datetime.now(datetime.timezone.utc)
        out.append({
            "slug": slug,
            "url": "https://immunefi.com" + m.group("url"),
            "kyc": m.group("kyc") == "true",
            "maxBounty": int(m.group("max")),
            "staleDays": (now - upd).days,
            "ageDays": (now - lau).days,
            "updated": upd.date().isoformat(),
            "launched": lau.date().isoformat(),
        })
    return out

def score(p):
    """ציון = תשואה פוטנציאלית מותאמת לטריות ולתחרות.

    השיקול המרכזי: maxBounty גבוה מסמן פרוטוקול עשיר, אבל גם פרוטוקול
    שנסרק אלף פעם. `ageDays` נמוך = פחות עיניים עברו על הקוד — זה
    היתרון האמיתי של מי שמגיע מאוחר לשוק. לכן גיל צעיר מקבל בונוס.
    """
    import math
    s = math.log10(max(p["maxBounty"], 1))          # 4–7 בערך
    s -= p["staleDays"] / 120.0                      # קנס על משלם ישן
    if p["ageDays"] < 180:  s += 1.2                 # תוכנית טרייה = קוד פחות סרוק
    elif p["ageDays"] < 400: s += 0.5
    return s

GH_RE = re.compile(r'github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)')

def repo_for(slug):
    """שולף owner/repo מדף ה-scope של התוכנית ב-Immunefi. None אם לא נמצא/נכשל."""
    url = f"https://immunefi.com/bug-bounty/{slug}/scope/"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
        m = GH_RE.search(html)
        return m.group(1).rstrip("/") if m else None
    except Exception:
        return None

def language_for(repo):
    """שולף primary language מ-GitHub API. None אם נכשל/לא ידוע."""
    try:
        req = urllib.request.Request(f"https://api.github.com/repos/{repo}",
                                      headers={"User-Agent": UA, "Accept": "application/vnd.github+json"})
        data = json.loads(urllib.request.urlopen(req, timeout=20).read())
        return data.get("language")
    except Exception:
        return None

EVM_LANGS = {"solidity", "vyper"}  # EVM = מתאים לכלים/ניסיון שלנו

def annotate_lang(live, limit=25):
    for p in live[:limit]:
        repo = repo_for(p["slug"])
        p["repo"] = repo
        p["language"] = language_for(repo) if repo else None
    return live

def limit_from(args, default=25):
    for a in args:
        if a.startswith("--limit="):
            try:
                return int(a.split("=", 1)[1])
            except ValueError:
                pass
    return default

def main():
    args = sys.argv[1:]
    limit = limit_from(args)
    progs = parse(fetch())
    if not progs:
        print("!! לא נמצאו רשומות — ייתכן שמבנה הדף השתנה. בדוק את REC.", file=sys.stderr)
        return 1
    total, nokyc = len(progs), sum(1 for p in progs if not p["kyc"])

    cand = progs if "--all" in args else [p for p in progs if not p["kyc"]]
    live = [p for p in cand if p["staleDays"] <= MAX_STALE_DAYS and p["maxBounty"] >= MIN_BOUNTY]
    live.sort(key=score, reverse=True)

    if "--lang" in args:
        annotate_lang(live, limit=limit)

    if "--json" in args:
        print(json.dumps(live, indent=2, ensure_ascii=False)); return 0

    print(f"Immunefi — {total} תוכניות סה\"כ | {nokyc} ללא KYC ({nokyc*100//total}%)")
    print(f"שערי חיוּת: עודכן ≤{MAX_STALE_DAYS} יום · באונטי ≥${MIN_BOUNTY:,}")
    print(f"עברו את הסינון: {len(live)} מתוך {len(cand)}\n")
    if "--lang" in args:
        print(f"{'#':<3}{'תוכנית':<26}{'מקס באונטי':>14}{'עודכן':>12}{'ישן':>6}{'גיל':>7}  ציון  שפה")
        print("-" * 96)
        for i, p in enumerate(live[:limit], 1):
            lang = p.get("language")
            flag = "" if lang and lang.lower() in EVM_LANGS else "  ⚠ non-EVM" if lang else "  ?"
            print(f"{i:<3}{p['slug'][:25]:<26}${p['maxBounty']:>13,}{p['updated']:>12}"
                  f"{p['staleDays']:>5}י{p['ageDays']:>6}י  {score(p):.2f}  {lang or '?'}{flag}")
    else:
        print(f"{'#':<3}{'תוכנית':<26}{'מקס באונטי':>14}{'עודכן':>12}{'ישן':>6}{'גיל':>7}  ציון")
        print("-" * 82)
        for i, p in enumerate(live[:limit], 1):
            print(f"{i:<3}{p['slug'][:25]:<26}${p['maxBounty']:>13,}{p['updated']:>12}"
                  f"{p['staleDays']:>5}י{p['ageDays']:>6}י  {score(p):.2f}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
