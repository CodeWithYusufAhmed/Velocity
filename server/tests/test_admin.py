"""Admin dashboard: auth gate, balance adjust with audit, report resolve."""

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.models import AdminAudit, Report, Transaction, User
from app.security import hash_password


async def _admin_user(db_session, email="admin@example.com"):
    from app.models import Credential
    u = User(email=email, display_name="Boss", balance=0, is_admin=True)
    db_session.add(u)
    await db_session.flush()
    db_session.add(Credential(user_id=u.id, password_hash=hash_password("s3cretpass")))
    await db_session.commit()
    return u


async def _login(client, monkeypatch, email="admin@example.com"):
    monkeypatch.setattr(get_settings(), "admin_password", "dashboards3cret")
    r = await client.post("/admin/login", data={
        "email": email, "password": "s3cretpass", "admin_password": "dashboards3cret"})
    assert r.status_code == 303
    return r.cookies


@pytest.mark.asyncio
async def test_admin_pages_require_auth(client):
    r = await client.get("/admin")
    assert r.status_code == 307 and r.headers["location"] == "/admin/login"


@pytest.mark.asyncio
async def test_non_admin_cannot_login(client, db_session, monkeypatch):
    from app.models import Credential
    u = User(email="pleb@example.com", display_name="Pleb", balance=0)
    db_session.add(u)
    await db_session.flush()
    db_session.add(Credential(user_id=u.id, password_hash=hash_password("s3cretpass")))
    await db_session.commit()
    monkeypatch.setattr(get_settings(), "admin_password", "dashboards3cret")
    r = await client.post("/admin/login", data={
        "email": "pleb@example.com", "password": "s3cretpass",
        "admin_password": "dashboards3cret"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_wrong_admin_password_rejected(client, db_session, monkeypatch):
    await _admin_user(db_session)
    monkeypatch.setattr(get_settings(), "admin_password", "dashboards3cret")
    r = await client.post("/admin/login", data={
        "email": "admin@example.com", "password": "s3cretpass", "admin_password": "wrong"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_adjust_balance_writes_ledger_and_audit(client, db_session, monkeypatch):
    admin = await _admin_user(db_session)
    target = User(email="t@example.com", display_name="Target", balance=1_000)
    db_session.add(target)
    await db_session.commit()
    cookies = await _login(client, monkeypatch)

    r = await client.post(f"/admin/users/{target.id}/adjust",
                          data={"amount": "5000", "note": "compensation"}, cookies=cookies)
    assert r.status_code == 303
    await db_session.refresh(target)
    assert target.balance == 6_000
    tx = await db_session.scalar(select(Transaction).where(Transaction.type == "admin_adjust"))
    assert tx.amount == 5_000 and tx.balance_after == 6_000
    audit = await db_session.scalar(select(AdminAudit))
    assert audit.action == "adjust_balance" and audit.admin_id == admin.id

    # Can't drive negative: -999999 clamps to zero.
    await client.post(f"/admin/users/{target.id}/adjust",
                      data={"amount": "-999999", "note": ""}, cookies=cookies)
    await db_session.refresh(target)
    assert target.balance == 0


@pytest.mark.asyncio
async def test_resolve_report(client, db_session, monkeypatch):
    admin = await _admin_user(db_session)
    other = User(email="o@example.com", display_name="O", balance=0)
    db_session.add(other)
    await db_session.flush()
    db_session.add(Report(reporter_id=other.id, reported_id=admin.id, reason="test"))
    await db_session.commit()
    cookies = await _login(client, monkeypatch)

    rep = await db_session.scalar(select(Report))
    r = await client.post(f"/admin/reports/{rep.id}/resolve", cookies=cookies)
    assert r.status_code == 303
    await db_session.refresh(rep)
    assert rep.status == "resolved" and rep.resolved_by == admin.id
