"""Settings from env vars — injected by `op run` (see scripts/run.sh).

One field per line in .env.tpl. Instantiate Settings() inside main(),
not at import time, so tests can run without secrets.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    notion_token: str
    new_contacts_max_tasks: int = 30
