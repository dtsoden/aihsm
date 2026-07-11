import pytest

from secret_harness import log


@pytest.fixture(autouse=True)
def isolate_secret_harness_log(tmp_path, monkeypatch):
    """Keep every test's logging inside tmp_path.

    Without this, any test that calls detect.run(...) or vault.main(...)
    without first configuring log.get_logger() explicitly would fall back to
    log.default_log_path(), which points at the real user's home directory.
    Patching default_log_path here means that fallback always lands in a
    throwaway tmp_path instead, so running the suite never writes log files
    outside of pytest's own tmp dirs. Tests in test_log.py that need a
    specific path still get one, since they pass log_path explicitly to
    get_logger(force=True), bypassing default_log_path entirely.
    """
    monkeypatch.setattr(log, "default_log_path", lambda: tmp_path / "auto-secret-harness.log")
    log._clear_handlers(log.logging.getLogger(log._LOGGER_NAME))
    log._configured = False
    yield
    log._clear_handlers(log.logging.getLogger(log._LOGGER_NAME))
    log._configured = False
