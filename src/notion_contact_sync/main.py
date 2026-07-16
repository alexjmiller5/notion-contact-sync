"""Launchd entrypoint (scripts/run.sh): runs every job in sequence.

Run a single job:  python -m notion_contact_sync.main enrich
Or directly:       python -m notion_contact_sync.enrich [--dry-run]
"""

import sys

import structlog

from notion_contact_sync import enrich, new_contacts

log = structlog.get_logger()

JOBS = {"enrich": enrich.run, "new_contacts": new_contacts.run}


def run(jobs: list[str] | None = None) -> dict:
    results = {name: JOBS[name]() for name in (jobs or list(JOBS))}
    log.info("all jobs done", jobs=list(results))
    return results


if __name__ == "__main__":
    names = sys.argv[1:]
    if unknown := set(names) - JOBS.keys():
        sys.exit(f"unknown job(s) {sorted(unknown)}; available: {list(JOBS)}")
    run(names or None)
