#!/bin/bash
# One-time (per machine): store the 1Password service-account token in the
# login Keychain so launchd runs can authenticate without a plaintext file.
# Run interactively — prompts via `op read` from your signed-in 1Password.
set -euo pipefail

USAGE="usage: store_op_token.sh <keychain-service-name> <op-ref>
  e.g. store_op_token.sh notion-contact-sync-op-token 'op://Personal/notion-contact-sync-ci SA Token/token'"
SERVICE="${1:?$USAGE}"
OP_REF="${2:?$USAGE}"
TOKEN=$(op read "$OP_REF")

security add-generic-password -U -s "$SERVICE" -a "$USER" -w "$TOKEN"
echo "stored token under Keychain service '$SERVICE'"
