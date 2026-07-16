"""Settings from env vars — injected by `op run` (see scripts/run.sh).

One field per line in .env.tpl. Instantiate Settings() inside main(),
not at import time, so tests can run without secrets.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    notion_token: str
    people_ds: str  # People data source id
    tasks_ds: str  # Tasks data source id
    project_page_id: str  # project page tasks get related to
    tags_prop: str = "Tags"  # People multi-select prop marking a contact as triaged
    new_contacts_max_tasks: int = 30
