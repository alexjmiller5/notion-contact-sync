"""The job. Plain Python — launchd runs this via scripts/run.sh."""

import structlog

log = structlog.get_logger()


def run() -> dict:
    log.info("job started")
    # TODO: parse data/ exports and sync into the Notion People DB
    return {"ok": True}


if __name__ == "__main__":
    run()
