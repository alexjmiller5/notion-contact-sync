# Notion Contact Source Unifier

Unifies contacts from every social platform's data export into the Notion
People DB. Runs as a scheduled job on the mac mini (mini-job template) since
inputs are manually-downloaded local export files.

## Sources

- Google Contacts
- Snapchat
- Instagram
- Facebook
- LinkedIn

## Key Notes

- definitely gonna need instructions about how to update the contact information with each source. Gonna need detailed instructions for each source and make sure the file structures match for each socials way of exporting them. Google contact should be easy because it has an api but gonna need to make sure my code is able to extract the proper data from the way the data is structured for each of the socials (instagram, facebook, snapchat, linkedin).

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

Scheduling via launchd is not wired up yet — needs nix-config integration
(add a second launchd agent or fold into the main job in `nix/darwin.nix`).

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
- `just store-op-token` — 1Password SA token → login Keychain
- Grant Full Disk Access if the job reads protected data (TCC is SIP-protected)

### Pending 1Password setup (TODO — needs Alex's desktop op session)

The claude-code service account cannot create vaults (403). Run:

```bash
op vault create "Notion Contact Sync"
OUT=$(op service-account create "notion-contact-sync-ci" --vault "Notion Contact Sync:read_items" --format json </dev/null)
op item create --category "API Credential" --title "notion-contact-sync-ci SA Token" --vault Personal "token[concealed]=$(echo "$OUT" | jq -r .token)" </dev/null
```

Then add a "Notion Integration Secret" item (field `credential`) to the new
vault, and bootstrap CI:

```bash
gh secret set OP_SERVICE_ACCOUNT_TOKEN --body "$(op read 'op://Personal/notion-contact-sync-ci SA Token/token')"
```
