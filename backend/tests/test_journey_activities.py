"""Journey activities called directly on fake storage and fake Meta, no Temporal involved."""

from datetime import UTC, datetime, timedelta

import pytest
from temporalio.exceptions import ApplicationError

from meta_client import MetaPermanentError, MetaTransientError
from tests._fakes import FakeDb, FakeMeta
from worker.activities.journey import (
    JourneyActivities,
    RunProgress,
    SendTemplateInput,
    SendTextInput,
)

PHONE = "+48600000001"


def seeded() -> tuple[FakeDb, FakeMeta, JourneyActivities]:
    db, meta = FakeDb(), FakeMeta()
    db.rows("contacts").append(
        {"id": "c-1", "phone_e164": PHONE, "first_name": "Ala", "attributes": {}}
    )
    db.rows("templates").append(
        {"id": "t-1", "name": "welcome_offer", "language": "pl", "status": "APPROVED"}
    )
    db.rows("journey_runs").append({"id": "r-1", "status": "running", "current_node_id": "start"})
    acts = JourneyActivities(db, meta, send_mode="test", allowlist={PHONE})
    return db, meta, acts


def request(**overrides: object) -> SendTemplateInput:
    base = {
        "run_id": "r-1",
        "workflow_id": "journey:j1:contact:c-1",
        "node_id": "n1",
        "visit": 1,
        "contact_id": "c-1",
        "template_id": "t-1",
        "body_values": ["Ala"],
    }
    return SendTemplateInput(**{**base, **overrides})  # type: ignore[arg-type]


@pytest.mark.anyio
async def test_send_template_inserts_then_sends_once() -> None:
    db, meta, acts = seeded()
    first = await acts.send_template(request())
    second = await acts.send_template(request())  # retry or replay after a crash
    assert (first.status, first.wamid) == ("sent", "wamid.T1")
    assert second == first
    assert len(meta.sent) == 1
    row = db.rows("messages")[0]
    assert (row["idempotency_key"], row["status"], row["wamid"]) == (
        "journey:j1:contact:c-1:n1:1",
        "sent",
        "wamid.T1",
    )
    assert row["meta_response"] == {"messages": [{"id": "wamid.T1"}]}
    assert len(db.rows("messages")) == 1


@pytest.mark.anyio
async def test_send_template_refuses_numbers_outside_the_allowlist() -> None:
    db, meta, acts = seeded()
    db.rows("contacts")[0]["phone_e164"] = "+48600000009"
    result = await acts.send_template(request())
    assert result.status == "failed" and "WA_ALLOWED_TEST_RECIPIENTS" in (result.error or "")
    assert meta.sent == []
    assert db.rows("messages")[0]["status"] == "failed"


@pytest.mark.anyio
async def test_send_template_requires_an_approved_template() -> None:
    db, _, acts = seeded()
    db.rows("templates")[0]["status"] = "PENDING"
    result = await acts.send_template(request())
    assert result.status == "failed" and "PENDING" in (result.error or "")


@pytest.mark.anyio
async def test_meta_permanent_error_fails_the_message_and_transient_error_retries() -> None:
    db, meta, acts = seeded()
    meta.send_error = MetaPermanentError("Meta 400: (#131026) Message undeliverable", code=131026)
    failed = await acts.send_template(request())
    assert failed.status == "failed"
    assert db.rows("messages")[0]["error"]["code"] == 131026

    meta.send_error = MetaTransientError("Meta 400: (#130429) Rate limit hit", code=130429)
    with pytest.raises(MetaTransientError):
        await acts.send_template(request(node_id="n2"))
    assert db.rows("messages")[1]["status"] == "pending"  # the retry will pick it up
    meta.send_error = None
    retried = await acts.send_template(request(node_id="n2"))
    assert retried.status == "sent" and len(meta.sent) == 1


@pytest.mark.anyio
async def test_missing_contact_or_unconfigured_meta_is_not_retried() -> None:
    db, _, acts = seeded()
    with pytest.raises(ApplicationError) as missing:
        await acts.load_contact("nope")
    assert missing.value.non_retryable
    no_meta = JourneyActivities(db, None, send_mode="test", allowlist={PHONE})
    with pytest.raises(ApplicationError) as unconfigured:
        await no_meta.send_template(request())
    assert unconfigured.value.non_retryable


@pytest.mark.anyio
async def test_check_consent_follows_the_latest_row() -> None:
    db, _, acts = seeded()
    assert not await acts.check_consent("c-1")
    db.rows("consents").append(
        {"contact_id": "c-1", "status": "opted_in", "captured_at": "2026-10-01T10:00:00+00:00"}
    )
    assert await acts.check_consent("c-1")
    db.rows("consents").append(
        {"contact_id": "c-1", "status": "opted_out", "captured_at": "2026-10-02T10:00:00+00:00"}
    )
    assert not await acts.check_consent("c-1")


@pytest.mark.anyio
async def test_update_contact_merges_attributes_and_sets_columns() -> None:
    db, _, acts = seeded()
    db.rows("contacts")[0]["attributes"] = {"vip": True}
    await acts.update_contact("c-1", {"attributes.interested": True, "locale": "pl"})
    contact = db.rows("contacts")[0]
    assert contact["attributes"] == {"vip": True, "interested": True}
    assert contact["locale"] == "pl"


@pytest.mark.anyio
async def test_record_run_progress_marks_terminal_runs() -> None:
    db, _, acts = seeded()
    await acts.record_run_progress(RunProgress("r-1", "n1"))
    run = db.rows("journey_runs")[0]
    assert (run["current_node_id"], run["status"]) == ("n1", "running")
    assert "ended_at" not in run
    await acts.record_run_progress(RunProgress("r-1", "end", status="completed"))
    assert run["status"] == "completed" and run["ended_at"].endswith("+00:00")


def text_request(**overrides: object) -> SendTextInput:
    base = {
        "run_id": "r-1",
        "workflow_id": "journey:j1:contact:c-1",
        "node_id": "n2",
        "visit": 1,
        "contact_id": "c-1",
        "text": "Cześć Ala",
    }
    return SendTextInput(**{**base, **overrides})  # type: ignore[arg-type]


def inbound(db: FakeDb, minutes_ago: int) -> None:
    received = (datetime.now(UTC) - timedelta(minutes=minutes_ago)).isoformat()
    db.rows("inbound_messages").append(
        {"contact_id": "c-1", "wamid": f"wamid.IN{minutes_ago}", "received_at": received}
    )


@pytest.mark.anyio
async def test_send_text_sends_once_inside_the_window() -> None:
    db, meta, acts = seeded()
    inbound(db, 30)
    first = await acts.send_text(text_request())
    second = await acts.send_text(text_request())  # retry or replay after a crash
    assert (first.status, first.wamid) == ("sent", "wamid.X1") and second == first
    assert meta.sent_texts == [(PHONE, "Cześć Ala")]
    row = db.rows("messages")[0]
    assert (row["kind"], row["text"], row["template_id"], row["status"]) == (
        "text",
        "Cześć Ala",
        None,
        "sent",
    )
    assert len(db.rows("messages")) == 1


@pytest.mark.anyio
async def test_send_text_skips_when_the_window_is_closed() -> None:
    db, meta, acts = seeded()
    inbound(db, 25 * 60)  # yesterday: outside the 24 hours
    result = await acts.send_text(text_request())
    assert result.status == "skipped" and meta.sent_texts == []
    assert db.rows("messages")[0]["status"] == "skipped"
    again = await acts.send_text(text_request())
    assert again.status == "skipped" and len(db.rows("messages")) == 1


@pytest.mark.anyio
async def test_send_text_fails_when_the_window_is_closed_and_the_node_says_fail() -> None:
    db, meta, acts = seeded()  # no inbound message at all
    result = await acts.send_text(text_request(if_closed="fail"))
    assert result.status == "failed" and "window" in (result.error or "")
    assert db.rows("messages")[0]["status"] == "failed" and meta.sent_texts == []


@pytest.mark.anyio
async def test_send_text_treats_metas_re_engagement_error_as_a_closed_window() -> None:
    db, meta, acts = seeded()
    inbound(db, 10)
    meta.send_error = MetaPermanentError("Meta 400: (#131047) Re-engagement message", code=131047)
    assert (await acts.send_text(text_request())).status == "skipped"
    assert db.rows("messages")[0]["status"] == "skipped"
