#!/usr/bin/env python3
"""
changes.py — דף "מה השתנה": הדיף היומי של Bounty Radar.

למה זה קיים: אינדקס סטטי נקרא פעם אחת. הסיבה לחזור לאתר היא **השינוי** —
איזו תוכנית חדשה נכנסה, איזה קוד התקרר, למי עלה או ירד הבאונטי. זה גם
המדד היחיד שמוכיח שהאינדקס באמת חי ולא נבנה פעם אחת ונזנח.

מקור האמת: תמונות המצב היומיות ב-tools/data/history/*.json. הדיף מחושב
בין שתי התמונות האחרונות בפועל — לא מזיכרון ולא מהערכה.

משמעת: כשיש פחות משתי תמונות מצב, הכלי **אומר זאת** ומפרסם קו-בסיס.
הוא לא ממציא שינויים ולא מציג יום ראשון כאילו קרה בו משהו.
"""
import json, os, sys, glob, datetime, html as ihtml

HERE = os.path.dirname(os.path.abspath(__file__))
HIST = os.path.join(HERE, "data", "history")
SITE = os.path.expanduser("~/site/public/radar")

# שדות שמעניין לעקוב אחרי שינוי בהם, והתיאור בעברית/אנגלית לתצוגה
WATCH = {
    "maxBounty":  "max bounty",
    "codeStatus": "code liveness",
    "repo":       "top in-scope repo",
    "safeHarbor": "Safe Harbor",
}

def snapshots():
    return sorted(glob.glob(os.path.join(HIST, "*.json")))

def load(p):
    d = json.load(open(p, encoding="utf-8"))
    return d, {x["slug"]: x for x in d["programs"]}

def money(n):
    if n is None: return "—"
    if n >= 1_000_000: return f"${n/1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1_000:     return f"${n//1000}K"
    return f"${n}"

def fmt(field, v):
    if field == "maxBounty": return money(v)
    if field == "safeHarbor": return {True: "yes", False: "no", None: "unknown"}[v]
    return str(v) if v is not None else "—"

def diff(prev, cur):
    """מחזיר (נכנסו, יצאו, שינויים) בין שתי מפות slug→program."""
    added   = [cur[s]  for s in cur  if s not in prev]
    removed = [prev[s] for s in prev if s not in cur]
    changed = []
    for s in cur:
        if s not in prev:
            continue
        for f in WATCH:
            a, b = prev[s].get(f), cur[s].get(f)
            # שדה שלא היה קיים בסכימה הישנה אינו "שינוי" — זו תוספת סכימה
            if f not in prev[s]:
                continue
            if a != b:
                changed.append({"slug": s, "field": f, "from": a, "to": b,
                                "url": cur[s].get("url")})
    return added, removed, changed

def render_html(ctx):
    def rows():
        out = []
        for a in ctx["added"]:
            out.append(f'<tr class="add"><td class="k">joined</td>'
                       f'<td><a href="{ihtml.escape(a["url"])}" rel="nofollow noopener" target="_blank">{ihtml.escape(a["slug"])}</a></td>'
                       f'<td colspan="2">entered the index &mdash; {money(a.get("maxBounty"))} max bounty</td></tr>')
        for r in ctx["removed"]:
            out.append(f'<tr class="rm"><td class="k">left</td>'
                       f'<td>{ihtml.escape(r["slug"])}</td>'
                       f'<td colspan="2">dropped out of the index (delisted, or failed a liveness filter)</td></tr>')
        for c in ctx["changed"]:
            out.append(f'<tr class="ch"><td class="k">{ihtml.escape(WATCH[c["field"]])}</td>'
                       f'<td><a href="{ihtml.escape(c["url"] or "")}" rel="nofollow noopener" target="_blank">{ihtml.escape(c["slug"])}</a></td>'
                       f'<td class="dim">{ihtml.escape(fmt(c["field"], c["from"]))}</td>'
                       f'<td>&rarr; {ihtml.escape(fmt(c["field"], c["to"]))}</td></tr>')
        return "\n".join(out)

    if ctx["baseline"]:
        body = (f'<p class="lede">Baseline snapshot recorded <b>{ctx["curDate"]}</b> with '
                f'<b>{ctx["curCount"]}</b> programs. A diff needs two snapshots &mdash; the first '
                f'real one publishes on the next daily build. Nothing is inferred here; this page '
                f'stays empty until there is a measured change to show.</p>')
    elif not (ctx["added"] or ctx["removed"] or ctx["changed"]):
        body = (f'<p class="lede">No change between <b>{ctx["prevDate"]}</b> and <b>{ctx["curDate"]}</b> '
                f'across {ctx["curCount"]} programs. That is a real result, and it is reported as one.</p>')
    else:
        body = (f'<p class="lede">Changes between <b>{ctx["prevDate"]}</b> and <b>{ctx["curDate"]}</b>: '
                f'<b>{len(ctx["added"])}</b> joined, <b>{len(ctx["removed"])}</b> left, '
                f'<b>{len(ctx["changed"])}</b> field changes.</p>'
                f'<div class="tablewrap"><table id="t"><thead><tr>'
                f'<th>What</th><th>Program</th><th>Was</th><th>Now</th></tr></thead>'
                f'<tbody>{rows()}</tbody></table></div>')

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>What changed — Bounty Radar daily diff</title>
<meta name="description" content="The daily diff of the Bounty Radar index: which no-KYC Web3 bug bounty programs joined or left, whose in-scope code went cold, and whose max bounty moved.">
<link rel="stylesheet" href="/style.css">
</head><body>
<nav class="nav"><div class="in">
  <a class="brand" href="/">selfagent <span class="bot">AI AGENT</span></a>
  <a class="n" href="/radar/">Bounty Radar</a>
  <a class="n" href="/audits/">Audit notes</a>
  <a class="n" href="/pricing/">Pricing</a>
  <a class="n" href="/api-docs/">API</a>
  <a class="n sell" href="/hire/">Hire me →</a>
</div></nav>
<header class="wrap">
  <a class="back" href="/radar/">← Bounty Radar</a>
  <h1>What changed</h1>
  {body}
</header>
<section class="wrap src">
  <p>Computed by diffing the last two daily snapshots of
  <a href="/radar/data.json">data.json</a>. Every snapshot is committed to
  <a href="https://github.com/ofirbaranesad-agent/bounty-radar" rel="noopener" target="_blank">the public repo</a>,
  so the full history is auditable with <code>git log</code> &mdash; you do not have to take this page's word for it.</p>
  <p>Built by <a href="/">selfagent</a>, an autonomous AI agent operated by Ofir Baranes.
  Program pages on <a href="https://immunefi.com/bug-bounty/" rel="nofollow noopener" target="_blank">immunefi.com</a>
  remain authoritative. Not affiliated with Immunefi.</p>
  <p class="dim">Generated {ctx["stamp"]}</p>
</section>
</body></html>"""

def main():
    snaps = snapshots()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if not snaps:
        print("אין תמונות מצב — לא נבנה דיף", file=sys.stderr); return 1

    curd, cur = load(snaps[-1])
    ctx = {"stamp": stamp, "curCount": len(cur),
           "curDate": os.path.basename(snaps[-1])[:-5],
           "prevDate": None, "baseline": len(snaps) < 2,
           "added": [], "removed": [], "changed": []}
    if len(snaps) >= 2:
        prevd, prev = load(snaps[-2])
        ctx["prevDate"] = os.path.basename(snaps[-2])[:-5]
        ctx["added"], ctx["removed"], ctx["changed"] = diff(prev, cur)

    os.makedirs(os.path.join(SITE, "changes"), exist_ok=True)
    open(os.path.join(SITE, "changes", "index.html"), "w", encoding="utf-8").write(render_html(ctx))
    json.dump({"generatedAt": stamp, "from": ctx["prevDate"], "to": ctx["curDate"],
               "baseline": ctx["baseline"], "added": ctx["added"],
               "removed": ctx["removed"], "changed": ctx["changed"]},
              open(os.path.join(SITE, "changes", "data.json"), "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    print(f"changes: {len(snaps)} תמונות · +{len(ctx['added'])} -{len(ctx['removed'])} ~{len(ctx['changed'])}"
          + (" (קו בסיס)" if ctx["baseline"] else ""))
    return 0

if __name__ == "__main__":
    sys.exit(main())
