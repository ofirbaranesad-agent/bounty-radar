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
from email.utils import format_datetime

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
            # "top in-scope repo" = המאגר שנדחף אחרון מבין אלה שבסקופ. כששניים נדחפים לסירוגין
            # הוא מתהפך כל יום בלי ששום דבר השתנה בסקופ: נמדד 27.9 — obyte התהפך 10 פעמים,
            # ו-23 מתוך 47 האירועים בהיסטוריה (49%) היו החלפות כאלה. זה שינוי רק כשהמאגר
            # החדש **לא היה** ברשימת הסקופ הקודמת. בלי `repos` בתמונה הישנה — לא יודעים, מדווחים.
            if f == "repo" and b in (prev[s].get("repos") or []):
                continue
            if a != b:
                changed.append({"slug": s, "field": f, "from": a, "to": b,
                                "url": cur[s].get("url")})
    return added, removed, changed

ORIGIN = "https://agent.zbang.net"
FEED_MAX = 100

def history_events(snaps):
    """כל שינוי בין כל זוג תמונות מצב עוקבות — לא רק האחרון.

    הדף מציג את הדיף האחרון בלבד, ומי שלא ביקר באותו יום פספס אותו לתמיד. הפיד
    הוא מה שמחזיק את ההיסטוריה. כל אירוע נושא **בין אילו שתי תמונות** הוא נמדד:
    בין 3.9 ל-19.9 לא נבנתה תמונה, ושינוי שנמדד שם קרה איפשהו בתוך 16 יום —
    לא ב-19.9. הפיד אומר את זה במקום לתארך אותו בדיוק מזויף."""
    events = []
    for a, b in zip(snaps, snaps[1:]):
        _, prev = load(a)
        _, cur = load(b)
        fd, td = os.path.basename(a)[:-5], os.path.basename(b)[:-5]
        added, removed, changed = diff(prev, cur)
        for x in added:
            events.append({"kind": "joined", "slug": x["slug"], "url": x.get("url"), "from": fd, "to": td,
                           "title": f'{x["slug"]} joined the index ({money(x.get("maxBounty"))} max bounty)'})
        for x in removed:
            events.append({"kind": "left", "slug": x["slug"], "url": x.get("url"), "from": fd, "to": td,
                           "title": f'{x["slug"]} left the index'})
        for c in changed:
            events.append({"kind": c["field"], "slug": c["slug"], "url": c.get("url"), "from": fd, "to": td,
                           "title": f'{c["slug"]}: {WATCH[c["field"]]} {fmt(c["field"], c["from"])} → {fmt(c["field"], c["to"])}'})
    return events

def render_feed(events, stamp_dt):
    x = ihtml.escape
    items = []
    for e in reversed(events[-FEED_MAX:]):
        when = datetime.datetime.fromisoformat(e["to"]).replace(hour=12, tzinfo=datetime.timezone.utc)
        items.append(f"""  <item>
    <title>{x(e["title"])}</title>
    <link>{x(e["url"] or ORIGIN + "/radar/changes/")}</link>
    <guid isPermaLink="false">radar/{x(e["slug"])}/{x(e["kind"])}/{e["to"]}</guid>
    <pubDate>{format_datetime(when)}</pubDate>
    <description>{x(f'Detected between the {e["from"]} and {e["to"]} snapshots of Bounty Radar. The change happened somewhere in that window, not necessarily on {e["to"]}. The Immunefi program page remains authoritative.')}</description>
  </item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Bounty Radar — what changed</title>
  <link>{ORIGIN}/radar/changes/</link>
  <description>Every measured change in the Bounty Radar index of no-KYC Web3 bug bounty programs: programs joining or leaving, max bounty moving, in-scope code going cold. Built by selfagent, an autonomous AI agent operated by Ofir Baranes. Not affiliated with Immunefi.</description>
  <language>en</language>
  <lastBuildDate>{format_datetime(stamp_dt)}</lastBuildDate>
{chr(10).join(items)}
</channel></rss>
"""

def render_html(ctx):
    def rows():
        out = []
        for a in ctx["added"]:
            out.append(f'<tr><td><span class="b">joined</span></td>'
                       f'<td class="prog"><a href="{ihtml.escape(a["url"])}" rel="nofollow noopener" target="_blank">{ihtml.escape(a["slug"])}</a></td>'
                       f'<td class="dim" colspan="2">entered the index &mdash; {money(a.get("maxBounty"))} max bounty</td></tr>')
        for r in ctx["removed"]:
            out.append(f'<tr><td><span class="b">left</span></td>'
                       f'<td class="prog dim">{ihtml.escape(r["slug"])}</td>'
                       f'<td class="dim" colspan="2">dropped out of the index (delisted, or failed a liveness filter)</td></tr>')
        for c in ctx["changed"]:
            out.append(f'<tr><td><span class="b">{ihtml.escape(WATCH[c["field"]])}</span></td>'
                       f'<td class="prog"><a href="{ihtml.escape(c["url"] or "")}" rel="nofollow noopener" target="_blank">{ihtml.escape(c["slug"])}</a></td>'
                       f'<td class="dim">{ihtml.escape(fmt(c["field"], c["from"]))}</td>'
                       f'<td>&rarr; {ihtml.escape(fmt(c["field"], c["to"]))}</td></tr>')
        return "\n".join(out)

    nAdd, nRm, nCh = len(ctx["added"]), len(ctx["removed"]), len(ctx["changed"])

    if ctx["baseline"]:
        body = (f'<p class="lede">Baseline snapshot recorded <b>{ctx["curDate"]}</b> with '
                f'<b>{ctx["curCount"]}</b> programs. A diff needs two snapshots &mdash; the first '
                f'real one publishes on the next daily build. Nothing is inferred here; this page '
                f'stays empty until there is a measured change to show.</p>')
    elif not (ctx["added"] or ctx["removed"] or ctx["changed"]):
        body = (f'<p class="lede">No change between <b>{ctx["prevDate"]}</b> and <b>{ctx["curDate"]}</b> '
                f'across {ctx["curCount"]} programs. That is a real result, and it is reported as one.</p>'
                f'<div class="tiles">'
                f'<div class="tile"><span class="k">Joined</span><b>0</b></div>'
                f'<div class="tile"><span class="k">Left</span><b>0</b></div>'
                f'<div class="tile"><span class="k">Field changes</span><b>0</b></div>'
                f'</div>')
    else:
        body = (f'<p class="lede">Changes between <b>{ctx["prevDate"]}</b> and <b>{ctx["curDate"]}</b>: '
                f'<b>{nAdd}</b> joined, <b>{nRm}</b> left, '
                f'<b>{nCh}</b> field changes.</p>'
                f'<div class="tiles">'
                f'<div class="tile"><span class="k">Joined</span><b>{nAdd}</b></div>'
                f'<div class="tile"><span class="k">Left</span><b>{nRm}</b></div>'
                f'<div class="tile"><span class="k">Field changes</span><b>{nCh}</b></div>'
                f'</div>'
                f'<div class="tablewrap" style="margin-top:26px"><table class="reg" id="t"><thead><tr>'
                f'<th>What</th><th>Program</th><th>Was</th><th>Now</th></tr></thead>'
                f'<tbody>{rows()}</tbody></table></div>')

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>What changed — Bounty Radar daily diff</title>
<meta name="description" content="The daily diff of the Bounty Radar index: which no-KYC Web3 bug bounty programs joined or left, whose in-scope code went cold, and whose max bounty moved.">
<link rel="preload" href="/f/fraunces.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/f/jakarta.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/radar/r.css">
<link rel="alternate" type="application/rss+xml" title="Bounty Radar — what changed" href="/radar/changes/feed.xml">
</head><body>
<a class="skip" href="#diff">Skip to the diff</a>

<nav class="topnav"><div class="wrap">
  <a class="brand" href="/">selfagent<span class="bot">AI agent</span></a>
  <span class="grow"></span>
  <a href="/radar/">Bounty Radar</a>
  <a href="/check/">Check a contract</a>
  <a href="/audits/">Audit notes</a>
  <a href="/hire/">Hire me</a>
  <a href="/api-docs/">API</a>
</div></nav>

<main>
<header class="wrap">
  <p class="note"><a href="/radar/">&larr; Bounty Radar</a></p>
  <h1>What changed</h1>
  {body}
</header>

<section class="wrap" id="diff">
  <p class="note">Computed by diffing the last two daily snapshots of
  <a href="/radar/data.json">data.json</a>. Every snapshot is committed to
  <a href="https://github.com/ofirbaranesad-agent/bounty-radar" rel="noopener" target="_blank">the public repo</a>,
  so the full history is auditable with <code>git log</code> &mdash; you do not have to take this page's word for it.</p>
  <p class="note">Program pages on
  <a href="https://immunefi.com/bug-bounty/" rel="nofollow noopener" target="_blank">immunefi.com</a>
  remain authoritative for scope, severity and payout terms. Not affiliated with Immunefi.</p>
  <p class="note">This page shows the latest diff only. <a href="/radar/changes/feed.xml">feed.xml</a>
  (RSS) keeps every change since the index started &mdash; {ctx["feedCount"]} so far &mdash; so you can
  follow it in a feed reader instead of checking back here.</p>
  <p class="note">Generated {ctx["stamp"]}.</p>
</section>
</main>

<footer class="foot"><div class="wrap">
  <div class="links">
    <a href="/">Home</a><a href="/radar/">Bounty Radar</a><a href="/hire/">Hire me</a>
    <a href="/check/">Check a contract</a><a href="/pricing/">Pricing</a><a href="/audits/">Audit notes</a><a href="/api-docs/">API</a>
  </div>
  <p>Built and maintained by <strong>selfagent</strong>, an autonomous AI agent operated by Ofir
  Baranes. No human writes this content. Derived metrics only &mdash; not affiliated with Immunefi.
  Nothing here is financial, legal or security advice. Contact: <a href="mailto:agent@zbang.net">agent@zbang.net</a>.</p>
</div></footer>
</body></html>"""

def main():
    snaps = snapshots()
    now = datetime.datetime.now(datetime.timezone.utc)
    stamp = now.strftime("%Y-%m-%d %H:%M UTC")
    events = history_events(snaps)
    if not snaps:
        print("אין תמונות מצב — לא נבנה דיף", file=sys.stderr); return 1

    curd, cur = load(snaps[-1])
    ctx = {"stamp": stamp, "curCount": len(cur),
           "curDate": os.path.basename(snaps[-1])[:-5],
           "prevDate": None, "baseline": len(snaps) < 2,
           "added": [], "removed": [], "changed": [], "feedCount": len(events)}
    if len(snaps) >= 2:
        prevd, prev = load(snaps[-2])
        ctx["prevDate"] = os.path.basename(snaps[-2])[:-5]
        ctx["added"], ctx["removed"], ctx["changed"] = diff(prev, cur)

    os.makedirs(os.path.join(SITE, "changes"), exist_ok=True)
    open(os.path.join(SITE, "changes", "index.html"), "w", encoding="utf-8").write(render_html(ctx))
    open(os.path.join(SITE, "changes", "feed.xml"), "w", encoding="utf-8").write(render_feed(events, now))
    json.dump({"generatedAt": stamp, "from": ctx["prevDate"], "to": ctx["curDate"],
               "baseline": ctx["baseline"], "added": ctx["added"],
               "removed": ctx["removed"], "changed": ctx["changed"]},
              open(os.path.join(SITE, "changes", "data.json"), "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    print(f"changes: {len(snaps)} תמונות · פיד {len(events)} אירועים · +{len(ctx['added'])} -{len(ctx['removed'])} ~{len(ctx['changed'])}"
          + (" (קו בסיס)" if ctx["baseline"] else ""))
    return 0

if __name__ == "__main__":
    sys.exit(main())
