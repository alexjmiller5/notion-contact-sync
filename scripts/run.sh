#!/bin/bash
# launchd entrypoint: pull the 1Password service-account token from the login
# Keychain (secret zero — stored once via `just store-op-token`), then run the
# job with secrets injected from .env.tpl. No plaintext secrets on disk.
set -euo pipefail

cd "${PROJECT_DIR:?PROJECT_DIR must be set (launchd EnvironmentVariables)}"

OP_SERVICE_ACCOUNT_TOKEN=$(security find-generic-password -s "${OP_TOKEN_KEYCHAIN_SERVICE:?}" -w)
export OP_SERVICE_ACCOUNT_TOKEN
export PYTHONPATH=src

exec op run --env-file=.env.tpl -- uv run python -m notion_contact_sync.main
