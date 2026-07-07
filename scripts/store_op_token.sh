#!/bin/bash
# One-time (per machine): store the 1Password service-account token in the
# login Keychain so launchd runs can authenticate without a plaintext file.
# Run interactively — prompts via `op read` from your signed-in 1Password.
set -euo pipefail

SERVICE="${1:?usage: store_op_token.sh <keychain-service-name>}"
TOKEN=$(op read "op://Personal/notion-contact-sync-ci SA Token/token")

security add-generic-password -U -s "$SERVICE" -a "$USER" -w "$TOKEN"
echo "stored token under Keychain service '$SERVICE'"
