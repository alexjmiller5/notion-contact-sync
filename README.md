# Notion Contact Source Unifier

Unifies contacts from every social platform's data export into the Notion
People DB. Runs as a scheduled job on a Mac (launchd via nix-darwin) since
inputs are manually-downloaded local export files.

This is personal infrastructure published for others to adapt: point it at
your own Notion via env vars (see `.env.tpl`). It expects a People database
with `Name` (title), `First Name`/`Last Name`/`Nickname` (rich_text),
`Instagram`/`Facebook` (url), `Snapchat`/`LinkedIn URL` (rich_text), and a
tags multi-select (`TAGS_PROP`, default `Tags`); and a Tasks database with
`Name` (title), `Status`, `Priority` (select), `Notes` (rich_text), and
`Project` (relation).

## Sources

- Google Contacts (planned — has a real API)
- Snapchat
- Instagram
- Facebook
- LinkedIn

Each source's export format differs; the per-platform parsers and manual
export procedures below keep them in sync.

## Layout

```
src/notion_contact_sync/   the job (plain Python)
data/                      raw platform exports (PII — gitignored, never commit)
  facebook/your_friends.json
  instagram/followers.json, following.json
  snapchat/friends.json
  linkedin/Complete_LinkedInDataExport_<date>/  (Connections.csv etc.)
scripts/run.sh             launchd entrypoint (Keychain op token → op run → uv run)
nix/darwin.nix             nix-darwin module (launchd user agent, schedule options)
flake.nix                  exposes darwinModules.default for nix-config to consume
.env.tpl                   secrets manifest (1Password op:// refs, committed)
justfile                   run / test / check / fmt / store-op-token
```

## New-contact triage

`src/notion_contact_sync/new_contacts.py` queries the People DB for anyone
whose Tags multi-select is empty and creates a low-priority
"Tag & categorize contact: <Name>" task in the Tasks DB, linked to the
Notion Contact Sync project. Processed people page ids are tracked in
`.state/new_contacts_processed.json` (gitignored) so re-runs never create
duplicates. Creations are capped per run (`NEW_CONTACTS_MAX_TASKS`, default
30) — the remainder is picked up by later runs.

```bash
op run --env-file=.env.tpl -- uv run python -m notion_contact_sync.new_contacts
```

The scheduled entrypoint (`notion_contact_sync.main`, invoked by
`scripts/run.sh`) runs enrichment then new-contact triage; missing exports are
skipped with a warning.

## Enrichment

`src/notion_contact_sync/enrich.py` parses the on-disk exports into a common
record and fills empty social-profile props on People pages — Instagram (url),
Facebook (url), Snapchat (rich_text username), LinkedIn URL (rich_text).
Matching is by normalized name (casefold, accents/punct/digits stripped;
Instagram usernames are compared letters-only against Name / First+Last /
Nickname+Last). Safety: writes only to EMPTY props, and only when exactly one
person matches exactly one export record; single-word person names are never
auto-matched. Everything ambiguous/unmatched lands in
`data/reports/enrichment-review-<date>.csv` (gitignored — PII) with a
`status` column (`unmatched`, `ambiguous_person`, `ambiguous_record`,
`matched_no_url`, `single_name_match`) for manual review.

Note: Facebook's export has names only (no profile URLs), so Facebook matches
always go to the review CSV as `matched_no_url`.

```bash
op run --env-file=.env.tpl -- uv run python -m notion_contact_sync.enrich --dry-run  # then without
```

## Manual export procedures (uncodifiable click-ops)

Each platform's export is a manual download; refresh them into `data/` before
a sync run. Detailed steps TODO per platform:

### Google Contacts
TODO — prefer the People API (has a real API; no manual export needed once
wired up). Fallback: contacts.google.com → Export → Google CSV.

### Snapchat
TODO — Snapchat app → Settings → My Data → submit request → download ZIP →
copy `friends.json` to `data/snapchat/`.

### Instagram
TODO — Accounts Center → Your information and permissions → Download your
information → JSON format → copy `followers.json` / `following.json` to
`data/instagram/`.

### Facebook
TODO — Accounts Center → Download your information → JSON format → copy
`your_friends.json` to `data/facebook/`.

### LinkedIn
TODO — Settings & Privacy → Data privacy → Get a copy of your data (full
archive) → unzip to `data/linkedin/Complete_LinkedInDataExport_<date>/`.

## Bootstrap

See the `new-project` skill, or the checklist in CLAUDE.md.

Manual one-time steps per machine (cannot be codified — keep documented here):
- `just store-op-token '<op://ref/to/SA token>'` — 1Password service-account
  token → login Keychain
- Grant Full Disk Access if the job reads protected data (TCC is SIP-protected)

1Password side: a vault holding the items referenced in `.env.tpl`
(`Notion Integration Secret` plus a `Notion Contact Sync ENV` item with your
Notion ids), and a service account scoped read-only to that vault whose token
goes in the Keychain above.
