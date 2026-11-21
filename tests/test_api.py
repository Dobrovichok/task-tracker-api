from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from uuid import UUID

import jwt
from sqlalchemy import update

from app.config import get_auth_settings
from app.models import Role, User
from app.security import ALGORITHM, AUDIENCE, ISSUER


PASSWORD = "example-password-for-tests"


def login_headers(client, email):
    response = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    assert response.json()["token_type"] == "bearer"
    assert response.json()["expires_in"] == 1800
    assert response.headers["Cache-Control"] == "no-store"
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def register_user(client, email):
    response = client.post("/auth/register", json={"email": email, "password": PASSWORD})
    assert response.status_code == 201, response.text
    return response.json(), login_headers(client, email)


def create_task(client, headers, **payload):
    response = client.post("/tasks", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_registration_login_and_profile(client, sessions):
    password = "secret"
    invalid = client.post("/auth/register", json={"email": "invalid", "password": password})
    assert invalid.status_code == 422
    assert password not in invalid.text
    assert client.post(
        "/auth/register", json={"email": "one@example.com", "password": PASSWORD, "role": "admin"}
    ).status_code == 422

    user, headers = register_user(client, "ONE@EXAMPLE.COM")
    assert user == {"id": user["id"], "email": "one@example.com", "role": "member"}
    assert client.get("/auth/me", headers=headers).json() == user
    with sessions() as session:
        assert session.get(User, UUID(user["id"])).password_hash.startswith("$argon2id$")

    duplicate = client.post("/auth/register", json={"email": "one@example.com", "password": PASSWORD})
    assert duplicate.status_code == 409
    wrong_password = client.post("/auth/login", json={"email": "one@example.com", "password": "wrong"})
    unknown_account = client.post("/auth/login", json={"email": "none@example.com", "password": "wrong"})
    assert wrong_password.status_code == unknown_account.status_code == 401
    assert wrong_password.json() == unknown_account.json()


def test_missing_invalid_and_expired_jwt(client):
    user, _ = register_user(client, "token@example.com")
    now = datetime.now(UTC)
    key = get_auth_settings().jwt_secret.get_secret_value()
    claims = {
        "sub": user["id"],
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now - timedelta(minutes=5),
        "exp": now - timedelta(minutes=1),
    }
    expired = jwt.encode(claims, key, algorithm=ALGORITHM)
    wrong_signature = jwt.encode(
        {**claims, "exp": now + timedelta(minutes=1)}, token_urlsafe(48), algorithm=ALGORITHM
    )
    missing = client.get("/tasks")
    assert missing.status_code == 401
    assert missing.headers["WWW-Authenticate"] == "Bearer"
    for token in ("invalid", expired, wrong_signature):
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/tasks", headers=headers)
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"


def test_task_permissions_and_role_changes(client, sessions):
    owner, owner_headers = register_user(client, "owner@example.com")
    peer, peer_headers = register_user(client, "peer@example.com")
    task = create_task(client, owner_headers, title="Private task")
    assert task["owner_id"] == owner["id"]
    path = f"/tasks/{task['id']}"

    assert client.get(path, headers=owner_headers).status_code == 200
    assert client.get("/tasks", headers=peer_headers, params={"owner_id": owner["id"]}).json()["total"] == 0
    assert client.get(path, headers=peer_headers).status_code == 404
    assert client.patch(path, headers=peer_headers, json={"title": "Other title"}).status_code == 404
    assert client.delete(path, headers=peer_headers).status_code == 404
    assert client.post(
        "/tasks", headers=peer_headers, json={"title": "Task", "owner_id": owner["id"]}
    ).status_code == 422

    with sessions.begin() as session:
        session.execute(update(User).where(User.id == UUID(peer["id"])).values(role=Role.ADMIN))

    assert client.get("/tasks", headers=peer_headers).json()["total"] == 1
    assert client.get(path, headers=peer_headers).status_code == 200
    changed = client.patch(path, headers=peer_headers, json={"status": "done"})
    assert changed.status_code == 200
    assert changed.json()["status"] == "done"
    deleted = client.delete(path, headers=peer_headers)
    assert deleted.status_code == 204 and deleted.content == b""
    assert client.get(path, headers=owner_headers).status_code == 404


def test_filters_and_pagination(client):
    _, headers = register_user(client, "pages@example.com")
    first = create_task(client, headers, title="Plan 100%", priority="high", due_date="2030-01-01")
    second = create_task(
        client, headers, title="Next", description="PLAN 100%", priority="high", due_date="2030-01-03"
    )
    create_task(client, headers, title="Plan 1000", priority="high", due_date="2030-01-01")
    create_task(client, headers, title="Plan 100%", status="done", priority="high", due_date="2030-01-01")
    create_task(client, headers, title="Plan 100%", due_date="2030-01-01")
    create_task(client, headers, title="Plan 100%", priority="high")

    query = {"q": "plan 100%", "priority": "high", "status": "todo", "due_to": "2030-01-03", "page_size": 1}
    for number, expected in [(1, [second]), (2, [first]), (3, [])]:
        response = client.get("/tasks", params={**query, "page": number}, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json() == {"items": expected, "page": number, "page_size": 1, "total": 2}


def test_task_input_validation_and_partial_update(client):
    _, headers = register_user(client, "patch@example.com")
    for payload in ({"title": "   "}, {"title": "Text\0"}, {"title": "Task", "due_date": "2030-02-30"}):
        assert client.post("/tasks", headers=headers, json=payload).status_code == 422
    for params in ({"page_size": 101}, {"page": 0}, {"status": "unknown"}, {"unknown": "x"}, {"q": "x\0"}):
        assert client.get("/tasks", headers=headers, params=params).status_code == 422

    task = create_task(client, headers, title="  Task  ", due_date="2030-01-01")
    assert task["title"] == "Task"
    path = f"/tasks/{task['id']}"
    for payload in ({}, {"title": None}, {"status": None}, {"owner_id": task["owner_id"]}):
        assert client.patch(path, headers=headers, json=payload).status_code == 422

    changed = client.patch(path, headers=headers, json={"due_date": None, "priority": "high"})
    assert changed.status_code == 200
    assert changed.json()["due_date"] is None
    assert changed.json()["priority"] == "high"
    assert changed.json()["title"] == "Task"
    assert datetime.fromisoformat(changed.json()["updated_at"]) >= datetime.fromisoformat(task["updated_at"])
