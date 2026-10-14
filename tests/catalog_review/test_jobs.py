from types import SimpleNamespace

import pytest
from conftest import sign_in
from test_lifecycle import journal

from services.catalog_review.jobs import PilotJobs
from services.catalog_review.security import ReviewError


def jobs(service, calls, ready=lambda: None):
    return PilotJobs(service,require_ready=ready,
                     mail_dispatcher=SimpleNamespace(dispatch=lambda *args:calls.append(("invitation",args)),
                                                     dispatch_retention=lambda *args:calls.append(("retention",args))),
                     blobs=service.test_blobs,scanner=SimpleNamespace(inspect=lambda **kw:True),
                     parser=SimpleNamespace(inspect=lambda **kw:True))


def test_jobs_bounded_scan_notice_and_expiry(backend):
    journal(backend)
    workspace, owner, _ = sign_in(backend)
    calls = []
    runner = jobs(backend,calls)
    backend.quarantine(owner,"statement.csv",b"a,b\n1,2",backend.test_blobs)
    assert runner.scan_tick() == {"processed":1,"status":"accepted_for_review"}
    assert runner.scan_tick()["status"] == "idle"
    assert runner.retention_tick()["notices_queued"] == 0
    backend.clock.advance(76*86400)
    assert runner.retention_tick()["notices_queued"] == 1
    assert calls[0][0] == "retention"
    assert runner.retention_tick()["notices_queued"] == 0
    backend.clock.advance(14*86400)
    assert runner.retention_tick()["access_stopped"] == 1
    assert runner.mail_tick()["processed"] == 0
    assert backend.deletion_journal.contains(workspace)


def test_disabled_gate_never_dispatches(backend):
    sign_in(backend)
    calls = []
    def blocked():
        raise RuntimeError("launch blocked")
    runner = jobs(backend,calls,blocked)
    for operation in (runner.scan_tick,runner.mail_tick,runner.retention_tick):
        with pytest.raises(RuntimeError,match="launch blocked"):
            operation()
    assert calls == []


def test_inventory_over_pilot_limit_pauses_work(backend):
    for i in range(6):
        sign_in(backend,"source-"+str(i))
    with pytest.raises(ReviewError,match="pilot_inventory_limit"):
        jobs(backend,[]).scan_tick()
