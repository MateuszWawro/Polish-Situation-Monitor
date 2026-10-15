"""Ingest entrypoint: one scheduler process, one isolated job per source."""

import logging
import os
from datetime import UTC, datetime
from typing import Any

import httpx
import psycopg
from apscheduler.schedulers.blocking import BlockingScheduler

from ingest.adsb_gps import AdsbGpsWorker
from ingest.base import Worker
from ingest.firms import FirmsWorker
from ingest.gddkia import GddkiaWorker
from ingest.gios import GiosWorker
from ingest.imgw_hydro import ImgwHydroStationsWorker, ImgwHydroWarningsWorker
from ingest.imgw_meteo import ImgwMeteoWorker

log = logging.getLogger("ingest")

WORKERS: list[Worker[Any]] = [
    ImgwMeteoWorker(),
    ImgwHydroWarningsWorker(),
    ImgwHydroStationsWorker(),
    GiosWorker(),
    FirmsWorker(),
    GddkiaWorker(),
    AdsbGpsWorker(),
]

RETENTION_SQL = [
    "UPDATE events SET raw = NULL WHERE raw IS NOT NULL AND fetched_at < now() - interval '7 days'",
    "DELETE FROM water_levels WHERE measured_at < now() - interval '7 days'",
    "DELETE FROM fetch_attempts WHERE started_at < now() - interval '30 days'",
]


def dsn() -> str:
    return os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")


def run_worker(worker: Worker[Any]) -> None:
    # Fresh connection per run: a broken connection in one source never leaks into another.
    try:
        with psycopg.connect(dsn(), autocommit=True) as conn, httpx.Client() as client:
            worker.run(conn, client)
    except Exception:
        log.exception("%s: could not start run", worker.source)


def purge_old() -> None:
    with psycopg.connect(dsn(), autocommit=True) as conn:
        for sql in RETENTION_SQL:
            conn.execute(sql)


def build_scheduler() -> BlockingScheduler:
    # max_instances=1 + coalesce: a slow source never stacks runs or blocks others
    scheduler = BlockingScheduler(
        timezone="UTC", job_defaults={"max_instances": 1, "coalesce": True}
    )
    for worker in WORKERS:
        scheduler.add_job(
            run_worker,
            "interval",
            args=[worker],
            id=f"{worker.source}{worker.id_prefix}",
            seconds=worker.interval_s,
            next_run_time=datetime.now(UTC),
        )
    scheduler.add_job(purge_old, "interval", id="purge_old", hours=6)
    return scheduler


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    scheduler = build_scheduler()
    log.info("ingest scheduler starting with %d jobs", len(scheduler.get_jobs()))
    scheduler.start()


if __name__ == "__main__":
    main()
