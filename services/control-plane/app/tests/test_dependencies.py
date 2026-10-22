from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import dependencies as dep


def _request(claims=None, event=True):
    scope = {}
    if event:
        scope["aws.event"] = {"requestContext": {"authorizer": {"jwt": {"claims": claims}}}}
    return SimpleNamespace(scope=scope)


class Resuming(Exception):
    pass


Resuming.__name__ = "DatabaseResumingException"


@pytest.fixture
def calls(monkeypatch):
    log = {"provisioned": []}
    monkeypatch.setattr(dep, "_provision_user",
                        lambda db, sub, email: log["provisioned"].append((sub, email)))
    return log


def test_existing_user_is_returned_without_provisioning(monkeypatch, calls):
    monkeypatch.setattr(dep, "_find_user", lambda db, sub: "USER")
    assert dep.get_current_user(_request({"sub": "s1", "email": "a@x.com"}), db=None) == "USER"
    assert calls["provisioned"] == []


def test_new_user_is_provisioned_from_claims(monkeypatch, calls):
    seen = iter([None, "NEW"])
    monkeypatch.setattr(dep, "_find_user", lambda db, sub: next(seen))
    user = dep.get_current_user(_request({"sub": "s1", "email": " a@x.com "}), db=None)
    assert user == "NEW"
    assert calls["provisioned"] == [("s1", "a@x.com")]


def test_new_user_without_email_claim_is_rejected(monkeypatch, calls):
    monkeypatch.setattr(dep, "_find_user", lambda db, sub: None)
    with pytest.raises(HTTPException) as e:
        dep.get_current_user(_request({"sub": "s1"}), db=None)
    assert e.value.status_code == 401 and "ID token" in e.value.detail
    assert calls["provisioned"] == []


def test_email_owned_by_another_identity_gives_409(monkeypatch, calls):
    monkeypatch.setattr(dep, "_find_user", lambda db, sub: None)  # still missing after the insert
    with pytest.raises(HTTPException) as e:
        dep.get_current_user(_request({"sub": "s1", "email": "a@x.com"}), db=None)
    assert e.value.status_code == 409


def test_missing_event_or_sub_is_401(calls):
    with pytest.raises(HTTPException) as e:
        dep.get_current_user(_request(event=False), db=None)
    assert e.value.status_code == 401
    with pytest.raises(HTTPException) as e:
        dep.get_current_user(_request({"email": "a@x.com"}), db=None)
    assert e.value.status_code == 401


def test_database_resuming_gives_503_with_retry_after(monkeypatch, calls):
    def boom(db, sub):
        raise Resuming()
    monkeypatch.setattr(dep, "_find_user", boom)
    with pytest.raises(HTTPException) as e:
        dep.get_current_user(_request({"sub": "s1", "email": "a@x.com"}), db=None)
    assert e.value.status_code == 503 and e.value.headers["Retry-After"] == "5"


def test_other_database_errors_are_not_masked(monkeypatch, calls):
    def boom(db, sub):
        raise RuntimeError("real bug")
    monkeypatch.setattr(dep, "_find_user", boom)
    with pytest.raises(RuntimeError):
        dep.get_current_user(_request({"sub": "s1", "email": "a@x.com"}), db=None)
