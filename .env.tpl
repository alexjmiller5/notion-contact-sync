# Canonical secrets manifest — 1Password secret references only, SAFE to commit.
# Local dev:  op run --env-file=.env.tpl -- <cmd>   (see justfile)
# On the mini: scripts/run.sh injects these via the Keychain-held op token.
#
# TODO: the "Notion Contact Sync" vault + notion-contact-sync-ci service
# account do not exist yet (vault creation needs desktop op auth — see README).
NOTION_TOKEN=op://Notion Contact Sync/Notion Integration Secret/credential
