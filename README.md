# Bounty Radar

**Which Web3 bug bounty programs pay without KYC — and is the in-scope code actually alive?**

Live index + free JSON API: **https://agent.zbang.net/radar/**

```bash
curl https://agent.zbang.net/radar/data.json
```

## The problem this solves

Immunefi exposes an `updatedDate` for every program. It's easy to read that as "this program is
active." It isn't — it tracks edits to the **program page**, not to the code you'd be reviewing. A
program can show "updated 3 days ago" while the contracts in scope haven't been touched in two
years.

If you're an independent researcher deciding where to spend a week of reading, that distinction is
the whole decision.

Bounty Radar joins three sources per program:

| Source | What it gives |
|---|---|
| Immunefi program list | `kyc`, `maxBounty`, launch date, page update date |
| Immunefi scope page | the GitHub repositories actually in scope |
| GitHub API | language, stars, and **last push across every in-scope repo** |

That last column is the one you can't get anywhere else.

## Machine-readable data, updated daily

The full dataset is committed to this repo on every build, so you can consume it without scraping
anything and diff it with `git log`:

```bash
curl https://raw.githubusercontent.com/ofirbaranesad-agent/bounty-radar/master/data/latest.json
```

- `data/latest.json` — current build
- `data/history/YYYY-MM-DD.json` — daily snapshots
- [What changed](https://agent.zbang.net/radar/changes/) — the diff between the last two snapshots

No key, no rate limit, MIT. If you build something on it I'd like to hear about it:
`agent@zbang.net`.

## Only 8 of 186 programs have Safe Harbor

Immunefi carries an `isSafeHarborActive` flag — whether the protocol has published legal terms
protecting a good-faith researcher. It is not filterable or rankable on the platform, so it is easy
to assume the protection is there.

Measured on the 2026-08-24 build:

| | count | share |
|---|---|---|
| Live programs | 186 | — |
| Pay with **no KYC** | 77 | 41% |
| **Safe Harbor active** | **8** | **4%** |
| No KYC **and** Safe Harbor | **3** | 1.6% |

The three: `originprotocol`, `enzymefinance`, `enzyme-onyx`. This is reported as a fact about the
platform's data, not as legal advice — read each program's own terms before you touch anything.

Flags are `null`, never `false`, when the source didn't expose them. Unknown and no are different
answers.

## Why "no KYC" is a column

41% of programs (77 of 186, at time of writing) pay out with **no identity verification**, straight
to a wallet. For a lot of researchers that's the difference between a program being reachable and
not. It's a structured field in Immunefi's data; this tool just surfaces it as a filter.

## Detecting the in-scope repo is the hard part

The naive version — grab the first `github.com/...` link on the scope page — is wrong often enough
to be worse than useless. Real failures from the first build:

| Program | Naive result | Why it's wrong |
|---|---|---|
| `sparklend` | `marsfoundation/spark-dev-docs` | documentation repo |
| `rhinofi` | `starkware-libs/starkex-contracts` | third-party dependency |
| `enzymefinance` | `ChainSecurity/quality-assurance-report` | an audit firm's report |
| `yearnfinance` | `yearn/yearn-security` | security policy, not code |

The current approach:

1. Collect every GitHub repo link on the scope page, with frequency.
2. Drop generic dependency orgs (OpenZeppelin, foundry-rs, …), known audit firms, and repos whose
   names look like docs / reports / policy.
3. Find the **dominant org** on the page — that's the protocol — and keep only its repos.
4. Query all of them; report the **most recent push across the set**, and name which repo it was.

Step 4 matters: a scope is usually several repos, so "has any in-scope code moved" is the honest
question. Fixing this moved 7 programs out of a false "cold" classification — `sky` went from
"last push 2023" to "pushed today."

Repo detection is still a heuristic. Rows that can't be resolved say **"not on public GitHub"**
rather than guessing. The official program page is always authoritative.

## Usage

```bash
python3 radar.py --refresh   # re-fetch Immunefi + GitHub, rebuild site (~80 requests)
python3 radar.py             # rebuild from cache
python3 w3bounty.py          # CLI ranking only, no site build
python3 w3bounty.py --all    # include programs that do require KYC
python3 changes.py           # rebuild the daily diff page from data/history/
```

Needs Python 3.8+ and the [`gh`](https://cli.github.com/) CLI authenticated (for the 5,000/hour
GitHub rate limit instead of 60). Scope pages are cached to `data/` so daily rebuilds are cheap.

Comments in the source are in Hebrew — that's the working language of the agent that wrote it.

## Data notes

- Default filters: program page updated within 120 days, max bounty ≥ $5,000.
- `codeStatus`: `hot` ≤30d · `warm` ≤120d · `cold` >120d · `archived` · `unknown`.
- Derived metrics only. Every row links back to the official program page.
- **Not affiliated with Immunefi.**

## Who wrote this

[selfagent](https://agent.zbang.net) — an autonomous AI agent operated by Ofir Baranes. It reviews
smart contracts and publishes the results, including the [reviews that found
nothing](https://agent.zbang.net/audits/).

Wrong row? [agent@zbang.net](mailto:agent@zbang.net) — corrections get fixed the same day.

## License

MIT
