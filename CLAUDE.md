# CLAUDE.md

notion-contact-sync: unifies contacts from social-platform data exports
(Snapchat, Instagram, Facebook, LinkedIn, Google Contacts) into the Notion
People DB. Runs on the mac mini (mini-job pattern) because the inputs are
manually-downloaded export files living locally in `data/`.

## Data

`data/` holds raw platform exports — **PII (friends lists, Connections.csv
with emails), gitignored, never commit**:

- `data/facebook/your_friends.json`
- `data/instagram/followers.json`, `following.json`
- `data/snapchat/friends.json`
- `data/linkedin/Complete_LinkedInDataExport_<date>/` (many CSVs; Connections.csv is the contact list)

Exports are manual click-ops — per-platform refresh procedures live in README.md.

## How it runs

nix-darwin launchd user agent (`nix/darwin.nix`) → `scripts/run.sh` →
`op run --env-file=.env.tpl -- uv run python -m notion_contact_sync.main`.

The module is consumed by the mac mini's nix-config
(github.com/alexjmiller5/nix-config) as a flake input — deploying means:
add this repo as an input there, enable `services.notion-contact-sync`,
`just switch`.

Secret zero: the 1Password service-account token lives in the login Keychain
(`just store-op-token`, one-time per machine). run.sh reads it with
`security find-generic-password`. No plaintext secrets on disk, ever.
NOTE: the project 1P vault + CI service account are not created yet — see
"Pending 1Password setup" in README.md.

## Stack

uv · pydantic-settings (env config) · httpx · structlog · pytest · ruff.
Logs land in `data/launchd.log` / `data/launchd.err.log` (gitignored).
Instantiate `Settings()` inside `main()`, never at import time.

## Commands

Standard verb set (see global CLAUDE.md) — the justfile is the interface,
not a script catalog; one-offs go in `scripts/` and run directly.

| Command | Purpose |
|---|---|
| `just run` (alias `dev`) | Execute the job locally with secrets injected |
| `just test` / `just check` / `just fmt` | pytest / ruff read-only / ruff fix |
| `just logs` | Tail launchd logs (on the mini) |
| `just store-op-token` | One-time Keychain setup per machine |

## TDD

Write the test in `tests/` first, then the `src/notion_contact_sync/` code.
