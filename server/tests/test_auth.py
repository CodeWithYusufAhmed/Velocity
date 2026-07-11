"""Auth tests: happy paths, abuse cases, rotation/replay, Google linking."""

import pytest

from app.rate_limit import limiter
from app.services import auth as auth_service

REG = {"email": "yusuf@example.com", "display_name": "Yusuf", "password": "s3cretpass"}


async def _register(client, **overrides):
    return await client.post("/auth/register", json={**REG, **overrides})


@pytest.mark.asyncio
async def test_register_and_login(client):
    r = await _register(client)
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["email"] == REG["email"]
    assert body["tokens"]["access_token"] and body["tokens"]["refresh_token"]

    r = await client.post("/auth/login", json={"email": REG["email"], "password": REG["password"]})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_duplicate_email_rejected(client):
    assert (await _register(client)).status_code == 201
    assert (await _register(client, display_name="Other")).status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("password", "short", 422),          # < 8 chars
        ("email", "not-an-email", 422),
        ("display_name", "x", 422),          # < 2 chars
    ],
)
async def test_register_validation(client, field, value, expected):
    assert (await _register(client, **{field: value})).status_code == expected


@pytest.mark.asyncio
async def test_wrong_password_and_unknown_email_same_error(client):
    await _register(client)
    r1 = await client.post("/auth/login", json={"email": REG["email"], "password": "wrongwrong"})
    r2 = await client.post("/auth/login", json={"email": "ghost@example.com", "password": "wrongwrong"})
    assert r1.status_code == r2.status_code == 401
    assert r1.json()["detail"] == r2.json()["detail"]  # no account enumeration


@pytest.mark.asyncio
async def test_protected_route_requires_valid_token(client):
    # /auth/logout is unauthenticated by design; use a fabricated bearer on refresh flow instead
    r = await client.post("/auth/refresh", json={"refresh_token": "made-up"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rotation_and_replay_detection(client):
    tokens = (await _register(client)).json()["tokens"]
    old = tokens["refresh_token"]

    r = await client.post("/auth/refresh", json={"refresh_token": old})
    assert r.status_code == 200
    new = r.json()["refresh_token"]
    assert new != old

    # Replaying the rotated token must fail AND revoke everything.
    assert (await client.post("/auth/refresh", json={"refresh_token": old})).status_code == 401
    assert (await client.post("/auth/refresh", json={"refresh_token": new})).status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(client):
    tokens = (await _register(client)).json()["tokens"]
    rt = tokens["refresh_token"]
    assert (await client.post("/auth/logout", json={"refresh_token": rt})).status_code == 204
    assert (await client.post("/auth/refresh", json={"refresh_token": rt})).status_code == 401


@pytest.mark.asyncio
async def test_login_rate_limit(client):
    limiter.enabled = True
    limiter.reset()
    statuses = []
    for _ in range(6):
        r = await client.post(
            "/auth/login", json={"email": "ghost@example.com", "password": "wrongwrong"}
        )
        statuses.append(r.status_code)
    limiter.enabled = False
    assert statuses[:5] == [401] * 5
    assert statuses[5] == 429  # 5/minute per IP, sixth attempt blocked


@pytest.mark.asyncio
async def test_google_login_creates_and_links(client, monkeypatch):
    def fake_verify(token, request, audience):
        assert token == "fake-google-token"
        return {"sub": "google-sub-123", "email": REG["email"], "name": "Yusuf G"}

    monkeypatch.setattr(auth_service.google_id_token, "verify_oauth2_token", fake_verify)

    # Existing email/password account gets LINKED, not duplicated.
    await _register(client)
    r = await client.post("/auth/google", json={"id_token": "fake-google-token"})
    assert r.status_code == 200
    assert r.json()["user"]["email"] == REG["email"]

    # Same sub again → same account.
    r2 = await client.post("/auth/google", json={"id_token": "fake-google-token"})
    assert r2.json()["user"]["id"] == r.json()["user"]["id"]


@pytest.mark.asyncio
async def test_google_login_invalid_token(client, monkeypatch):
    def fake_verify(token, request, audience):
        raise ValueError("bad token")

    monkeypatch.setattr(auth_service.google_id_token, "verify_oauth2_token", fake_verify)
    r = await client.post("/auth/google", json={"id_token": "garbage"})
    assert r.status_code == 401
