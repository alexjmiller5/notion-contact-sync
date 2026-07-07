set shell := ["bash", "-cu"]
export PYTHONPATH := "src"

default:
    @just --list

# Execute the job locally with secrets injected
run:
    op run --env-file=.env.tpl -- uv run python -m notion_contact_sync.main

alias dev := run

test:
    uv run pytest

# All static analysis (read-only, CI-safe)
check:
    uv run ruff check . && uv run ruff format --check .

fmt:
    uv run ruff format . && uv run ruff check --fix .

# Tail the launchd logs (on the mini)
logs:
    tail -F data/launchd.log data/launchd.err.log

# One-time per machine: put the 1Password SA token in the login Keychain
store-op-token:
    ./scripts/store_op_token.sh notion-contact-sync-op-token

# --- project-specific recipes below (one-offs live in scripts/, run directly) ---
