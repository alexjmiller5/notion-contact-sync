"""Enrich People DB social-profile props from on-disk platform exports.

Run: op run --env-file=.env.tpl -- uv run python -m notion_contact_sync.enrich [--dry-run]

Sources -> target People props (must already exist; never created here):
  instagram -> Instagram (url)      value: profile URL
  facebook  -> Facebook (url)       export has names only, no URLs -> review CSV
  snapchat  -> Snapchat (rich_text) value: username
  linkedin  -> LinkedIn URL (rich_text) value: profile URL

Safety: writes only when the target prop is EMPTY; auto-applies only when
exactly one person matches the normalized name AND exactly one export record
carries that name. Everything ambiguous/unmatched lands in a review CSV under
data/reports/ (gitignored — PII).
"""

import csv
import json
import sys
import time
import unicodedata
from datetime import date
from pathlib import Path

import httpx
import structlog

from notion_contact_sync.config import Settings

log = structlog.get_logger()

API = "https://api.notion.com/v1"
DATA = Path(__file__).parents[2] / "data"
SOURCE_PROP = {
    "instagram": "Instagram",
    "facebook": "Facebook",
    "snapchat": "Snapchat",
    "linkedin": "LinkedIn URL",
}


def normalize(s: str) -> str:
    """Casefold, strip accents, keep letters only (drops digits/punct/spaces/emoji)."""
    decomposed = unicodedata.normalize("NFKD", s)
    return "".join(c for c in decomposed if c.isalpha() and not unicodedata.combining(c)).casefold()


# --- parsers: common record {source, username, display_name, profile_url} ---


def _record(source: str, username: str = "", display_name: str = "", profile_url: str = "") -> dict:
    return {
        "source": source,
        "username": username,
        "display_name": display_name,
        "profile_url": profile_url,
    }


def parse_instagram(followers_path: Path, following_path: Path) -> list[dict]:
    entries = json.loads(followers_path.read_text())
    entries += json.loads(following_path.read_text())["relationships_following"]
    by_username: dict[str, dict] = {}
    for e in entries:
        for s in e["string_list_data"]:
            by_username[s["value"]] = _record(
                "instagram", username=s["value"], profile_url=s["href"]
            )
    return list(by_username.values())


def parse_facebook(path: Path) -> list[dict]:
    friends = json.loads(path.read_text())["friends_v2"]
    return [_record("facebook", display_name=f["name"]) for f in friends]


def parse_snapchat(path: Path) -> list[dict]:
    friends = json.loads(path.read_text())["Friends"]  # only actual friends, not blocked/pending
    return [
        _record("snapchat", username=f["Username"], display_name=f["Display Name"]) for f in friends
    ]


def parse_linkedin(path: Path) -> list[dict]:
    lines = path.read_text().splitlines()
    header = next(i for i, line in enumerate(lines) if line.startswith("First Name,"))
    return [
        _record(
            "linkedin",
            display_name=f"{row['First Name']} {row['Last Name']}".strip(),
            profile_url=row["URL"],
        )
        for row in csv.DictReader(lines[header:])
    ]


# --- matching ---


def _rich_text(person: dict, prop: str) -> str:
    return "".join(t["plain_text"] for t in person["properties"][prop]["rich_text"])


def person_display(person: dict) -> str:
    return "".join(t["plain_text"] for t in person["properties"]["Name"]["title"])


def build_people_index(people: list[dict]) -> dict[str, list[dict]]:
    """normalized-name key -> people. Keys: Name, First+Last, Nickname+Last."""
    index: dict[str, list[dict]] = {}
    for p in people:
        first, last, nick = (_rich_text(p, f) for f in ("First Name", "Last Name", "Nickname"))
        keys = {
            normalize(person_display(p)),
            normalize(first + last),
            normalize(nick + last) if nick else "",
        }
        keys.discard("")
        for k in keys:
            if p not in index.setdefault(k, []):
                index[k].append(p)
    return index


def _record_key(rec: dict) -> str:
    # IG usernames double as the name ("jane.doe_99" -> "janedoe"); others have real names
    return normalize(rec["username"] if rec["source"] == "instagram" else rec["display_name"])


def _record_value(rec: dict) -> str:
    return rec["username"] if rec["source"] == "snapchat" else rec["profile_url"]


def _prop_empty(person: dict, prop: str) -> bool:
    p = person["properties"][prop]
    return p["url"] is None if "url" in p else not p["rich_text"]


def match(records: list[dict], index: dict[str, list[dict]]) -> tuple[list[dict], list[dict]]:
    """Returns (applies, review_rows).

    applies: {person_id, person_name, prop, value, source}
    review_rows: record + {status, candidates}; statuses: unmatched,
    ambiguous_person, ambiguous_record, matched_no_url, single_name_match.
    """
    groups: dict[tuple[str, str], dict[str, dict]] = {}  # (source, key) -> value -> record
    applies: list[dict] = []
    review: list[dict] = []

    def to_review(rec: dict, status: str, people: list[dict] | None = None) -> None:
        candidates = "; ".join(f"{person_display(p)} ({p['url']})" for p in people or [])
        review.append({**rec, "status": status, "candidates": candidates})

    for rec in records:
        key = _record_key(rec)
        if not key:
            to_review(rec, "unmatched")
            continue
        groups.setdefault((rec["source"], key), {})[_record_value(rec)] = rec

    for (_, key), by_value in groups.items():
        recs = list(by_value.values())  # identical duplicates already collapsed
        people = index.get(key, [])
        if not people:
            for rec in recs:
                to_review(rec, "unmatched")
        elif len(people) > 1:
            for rec in recs:
                to_review(rec, "ambiguous_person", people)
        elif len(recs) > 1:
            for rec in recs:
                to_review(rec, "ambiguous_record", people)
        else:
            rec, person = recs[0], people[0]
            value = _record_value(rec)
            if not value:
                to_review(rec, "matched_no_url", people)
            elif len(person_display(person).split()) < 2:
                # ponytail: one-word person names ("Alexa") match too loosely — defer to Alex
                to_review(rec, "single_name_match", people)
            elif _prop_empty(person, SOURCE_PROP[rec["source"]]):
                applies.append(
                    {
                        "person_id": person["id"],
                        "person_name": person_display(person),
                        "prop": SOURCE_PROP[rec["source"]],
                        "value": value,
                        "source": rec["source"],
                    }
                )
            # else: prop already filled — Alex's data wins, silent skip
    return applies, review


# --- Notion I/O ---


def fetch_all_people(client: httpx.Client, people_ds: str) -> list[dict]:
    results: list[dict] = []
    cursor: str | None = None
    while True:
        body: dict = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        resp = client.post(f"{API}/data_sources/{people_ds}/query", json=body)
        resp.raise_for_status()
        data = resp.json()
        results.extend(data["results"])
        if not data["has_more"]:
            return results
        cursor = data["next_cursor"]
        time.sleep(0.35)


def apply_one(client: httpx.Client, a: dict) -> None:
    payload = (
        {"url": a["value"]}
        if a["prop"] in ("Instagram", "Facebook")
        else {"rich_text": [{"text": {"content": a["value"]}}]}
    )
    client.patch(
        f"{API}/pages/{a['person_id']}", json={"properties": {a["prop"]: payload}}
    ).raise_for_status()


def linkedin_connections() -> Path:
    """Newest LinkedIn export dir (by mtime) — the dated dir name changes per download."""
    exports = list((DATA / "linkedin").glob("Complete_LinkedInDataExport_*"))
    if not exports:
        raise FileNotFoundError(f"no {DATA}/linkedin/Complete_LinkedInDataExport_* export found")
    return max(exports, key=lambda p: p.stat().st_mtime) / "Connections.csv"


def load_records() -> list[dict]:
    records: list[dict] = []
    sources = [
        (
            "instagram",
            lambda: parse_instagram(
                DATA / "instagram/followers.json", DATA / "instagram/following.json"
            ),
        ),
        ("facebook", lambda: parse_facebook(DATA / "facebook/your_friends.json")),
        ("snapchat", lambda: parse_snapchat(DATA / "snapchat/friends.json")),
        ("linkedin", lambda: parse_linkedin(linkedin_connections())),
    ]
    for name, parse in sources:
        try:
            recs = parse()
        except FileNotFoundError as e:
            log.warning("export missing, source skipped", source=name, missing=str(e))
            continue
        log.info("parsed export", source=name, records=len(recs))
        records += recs
    return records


def run(dry_run: bool = False) -> dict:
    settings = Settings()
    headers = {
        "Authorization": f"Bearer {settings.notion_token}",
        "Notion-Version": "2026-03-11",
        "Content-Type": "application/json",
    }
    records = load_records()
    with httpx.Client(headers=headers, timeout=30) as client:
        people = fetch_all_people(client, settings.people_ds)
        log.info("people cached", count=len(people))
        applies, review = match(records, build_people_index(people))
        if not dry_run:
            for a in applies:
                apply_one(client, a)
                log.info("applied", **a)
                time.sleep(0.35)  # Notion 3 rps

    report = DATA / "reports" / f"enrichment-review-{date.today().isoformat()}.csv"
    report.parent.mkdir(parents=True, exist_ok=True)
    fields = ["source", "username", "display_name", "profile_url", "status", "candidates"]
    with report.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(sorted(review, key=lambda r: (r["status"], r["source"])))

    applied_by_source = {s: sum(1 for a in applies if a["source"] == s) for s in SOURCE_PROP}
    summary = {
        "dry_run": dry_run,
        "applied": applied_by_source,
        "review_rows": len(review),
        "review_csv": str(report),
    }
    log.info("enrich done", **summary)
    return summary


if __name__ == "__main__":
    run(dry_run="--dry-run" in sys.argv)
