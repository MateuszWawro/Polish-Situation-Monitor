from ingest.main import build_scheduler


def test_scheduler_job_defaults() -> None:
    scheduler = build_scheduler()
    assert scheduler._job_defaults["max_instances"] == 1
    assert scheduler._job_defaults["coalesce"] is True
