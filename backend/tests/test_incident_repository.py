import uuid

import pytest

from backend.app.core.database import SessionLocal
from backend.app.models.incident import Incident
from backend.app.repositories.incident_repository import (
    IncidentRepository,
)


@pytest.fixture
def db():
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_incident():
    return Incident(
        incident_id=f"test-{uuid.uuid4()}",
        service="test-payment-service",
        namespace="aegis-test",
        environment="test",
        status="CrashLoopBackOff",
        recent_log="Database connection refused",
    )


def test_create_and_get_incident(db, test_incident):
    repository = IncidentRepository(db)

    try:
        record = repository.create(test_incident)

        assert record.incident_id == test_incident.incident_id
        assert record.service == "test-payment-service"
        assert record.namespace == "aegis-test"
        assert record.environment == "test"
        assert record.status == "CrashLoopBackOff"
        assert record.recent_log == "Database connection refused"
        assert record.lifecycle_state == "DETECTED"
        assert record.lifecycle_message == "Incident detected."

        fetched = repository.get_by_incident_id(
            test_incident.incident_id
        )

        assert fetched is not None
        assert fetched.incident_id == test_incident.incident_id
        assert fetched.service == test_incident.service

    finally:
        repository.delete(test_incident.incident_id)


def test_to_incident(db, test_incident):
    repository = IncidentRepository(db)

    try:
        record = repository.create(test_incident)

        incident = repository.to_incident(record)

        assert incident.incident_id == test_incident.incident_id
        assert incident.service == test_incident.service
        assert incident.namespace == test_incident.namespace
        assert incident.environment == test_incident.environment
        assert incident.status == test_incident.status
        assert incident.recent_log == test_incident.recent_log

    finally:
        repository.delete(test_incident.incident_id)


def test_update_incident(db, test_incident):
    repository = IncidentRepository(db)

    try:
        record = repository.create(test_incident)

        record.status = "Recovered"
        record.lifecycle_state = "RECOVERED"
        record.lifecycle_message = "Incident recovered."

        updated = repository.update(record)

        assert updated.status == "Recovered"
        assert updated.lifecycle_state == "RECOVERED"
        assert updated.lifecycle_message == "Incident recovered."

        fetched = repository.get_by_incident_id(
            test_incident.incident_id
        )

        assert fetched is not None
        assert fetched.status == "Recovered"
        assert fetched.lifecycle_state == "RECOVERED"

    finally:
        repository.delete(test_incident.incident_id)


def test_get_by_lifecycle_state(db, test_incident):
    repository = IncidentRepository(db)

    try:
        record = repository.create(test_incident)

        records = repository.get_by_lifecycle_state(
            "DETECTED"
        )

        incident_ids = {
            item.incident_id
            for item in records
        }

        assert record.incident_id in incident_ids

    finally:
        repository.delete(test_incident.incident_id)


def test_get_pending_approvals(db, test_incident):
    repository = IncidentRepository(db)

    try:
        record = repository.create(test_incident)

        record.lifecycle_state = "AWAITING_APPROVAL"
        record.lifecycle_message = (
            "Waiting for human approval."
        )

        repository.update(record)

        pending = repository.get_pending_approvals()

        incident_ids = {
            item.incident_id
            for item in pending
        }

        assert test_incident.incident_id in incident_ids

    finally:
        repository.delete(test_incident.incident_id)


def test_delete_incident(db, test_incident):
    repository = IncidentRepository(db)

    record = repository.create(test_incident)

    assert (
        repository.get_by_incident_id(
            test_incident.incident_id
        )
        is not None
    )

    deleted = repository.delete(
        test_incident.incident_id
    )

    assert deleted is True

    assert (
        repository.get_by_incident_id(
            test_incident.incident_id
        )
        is None
    )


def test_delete_nonexistent_incident(db):
    repository = IncidentRepository(db)

    deleted = repository.delete(
        f"non-existent-{uuid.uuid4()}"
    )

    assert deleted is False


def test_get_all_returns_persisted_incident(
    db,
    test_incident,
):
    repository = IncidentRepository(db)

    try:
        record = repository.create(test_incident)

        records = repository.get_all()

        incident_ids = {
            item.incident_id
            for item in records
        }

        assert record.incident_id in incident_ids

    finally:
        repository.delete(test_incident.incident_id)
