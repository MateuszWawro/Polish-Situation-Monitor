"""Ingest entrypoint: one scheduler process, one job per source (workers added in later steps)."""

import logging

from apscheduler.schedulers.blocking import BlockingScheduler

log = logging.getLogger("ingest")


def build_scheduler() -> BlockingScheduler:
    # max_instances=1 + coalesce: a slow source never stacks runs or blocks others
    return BlockingScheduler(timezone="UTC", job_defaults={"max_instances": 1, "coalesce": True})


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    scheduler = build_scheduler()
    log.info("ingest scheduler starting with %d jobs", len(scheduler.get_jobs()))
    scheduler.start()


if __name__ == "__main__":
    main()
