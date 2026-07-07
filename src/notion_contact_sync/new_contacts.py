"""New-contact triage: create a Tasks-DB task for each untagged person in the People DB.

Run: op run --env-file=.env.tpl -- uv run python -m notion_contact_sync.new_contacts

Dedup: processed people page ids are tracked in .state/new_contacts_processed.json
(gitignored) — re-runs skip anyone already handled. Creations are capped per run
(NEW_CONTACTS_MAX_TASKS, default 30) so the Tasks DB isn't flooded; uncapped
remainder is picked up by later runs.
"""

import json
import time
from pathlib import Path

import httpx
import structlog

from notion_contact_sync.config import Settings

log = structlog.get_logger()

API = "https://api.notion.com/v1"
PEOPLE_DS = "1a803953-a8af-80ab-824d-000bfe407316"
TASKS_DS = "77ef5074-aa23-468a-b5fb-2692e78184db"
PROJECT_PAGE_ID = "31103953-a8af-8109-890a-c3b303864590"
TAGS_PROP = "Tags (This will absorb gcontacts labels)"
STATE_FILE = Path(__file__).parents[2] / ".state" / "new_contacts_processed.json"


def fetch_untagged_people(client: httpx.Client) -> list[dict]:
    results: list[dict] = []
    cursor: str | None = None
    while True:
        body: dict = {
            "filter": {"property": TAGS_PROP, "multi_select": {"is_empty": True}},
            "sorts": [{"property": "Created time", "direction": "ascending"}],
            "page_size": 100,
        }
        if cursor:
            body["start_cursor"] = cursor
        resp = client.post(f"{API}/data_sources/{PEOPLE_DS}/query", json=body)
        resp.raise_for_status()
        data = resp.json()
        results.extend(data["results"])
        if not data["has_more"]:
            return results
        cursor = data["next_cursor"]


def person_name(person: dict) -> str:
    return "".join(t["plain_text"] for t in person["properties"]["Name"]["title"]) or "(unnamed)"


def task_payload(person: dict) -> dict:
    return {
        "parent": {"type": "data_source_id", "data_source_id": TASKS_DS},
        "properties": {
            "Name": {
                "title": [{"text": {"content": f"Tag & categorize contact: {person_name(person)}"}}]
            },
            "Status": {"status": {"name": "To Do"}},
            "Priority": {"select": {"name": "Low"}},
            "Notes": {"rich_text": [{"text": {"content": person["url"]}}]},
            "Project": {"relation": [{"id": PROJECT_PAGE_ID}]},
        },
    }


def run(max_tasks: int | None = None, state_path: Path = STATE_FILE) -> dict:
    settings = Settings()
    if max_tasks is None:
        max_tasks = settings.new_contacts_max_tasks
    processed: set[str] = set(json.loads(state_path.read_text())) if state_path.exists() else set()
    headers = {
        "Authorization": f"Bearer {settings.notion_token}",
        "Notion-Version": "2026-03-11",
        "Content-Type": "application/json",
    }
    created = skipped = remaining = 0
    with httpx.Client(headers=headers, timeout=30) as client:
        people = fetch_untagged_people(client)
        for person in people:
            if person["id"] in processed:
                skipped += 1
                continue
            if created >= max_tasks:
                remaining += 1
                continue
            client.post(f"{API}/pages", json=task_payload(person)).raise_for_status()
            processed.add(person["id"])
            created += 1
            log.info("task created", person=person_name(person))
            time.sleep(0.35)  # ponytail: Notion 3 req/s limit; fine for <=30 creates
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(sorted(processed)))
    summary = {"created": created, "skipped": skipped, "remaining": remaining}
    log.info("new_contacts done", total_untagged=len(people), **summary)
    return summary


if __name__ == "__main__":
    run()
