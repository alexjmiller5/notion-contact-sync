# Canonical secrets manifest — 1Password secret references only, SAFE to commit.
# Local dev:  op run --env-file=.env.tpl -- <cmd>   (see justfile)
# On the mini: scripts/run.sh injects these via the Keychain-held op token.
NOTION_TOKEN=op://Notion Contact Sync/Notion Integration Secret/credential
# Notion ids for YOUR workspace (People DB, Tasks DB, project page) — one field
# per var in the "Notion Contact Sync ENV" item.
PEOPLE_DS=op://Notion Contact Sync/Notion Contact Sync ENV/PEOPLE_DS
TASKS_DS=op://Notion Contact Sync/Notion Contact Sync ENV/TASKS_DS
PROJECT_PAGE_ID=op://Notion Contact Sync/Notion Contact Sync ENV/PROJECT_PAGE_ID
# Optional — People multi-select prop used for triage (defaults to "Tags").
TAGS_PROP=op://Notion Contact Sync/Notion Contact Sync ENV/TAGS_PROP
