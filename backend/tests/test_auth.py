"""API tests for authentication (signup / login / me).

TEACHING NOTE — auth tests earn their keep on the NEGATIVE paths: the
happy path failing is obvious in dev, but a token that still works after
account deactivation, or a 401 that leaks *why* login failed, is exactly
the kind of bug only a test catches early.
"""

from fastapi.testclient import TestClient

SIGNUP = {
    "email": "grace@example.com",
    "full_name": "Grace Hopper",
    "password": "correct-horse-battery",
}


def signup(client: TestClient, **overrides) -> dict:
    response = client.post("/v1/auth/signup", json={**SIGNUP, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


def login(client: TestClient, email: str, password: str):
    # OAuth2 password flow: FORM body (data=), and the field is named
    # "username" by spec even though we put an email in it.
    return client.post("/v1/auth/login", data={"username": email, "password": password})


def auth_header(client: TestClient) -> dict:
    signup(client)
    token = login(client, SIGNUP["email"], SIGNUP["password"]).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# --- signup -----------------------------------------------------------------
def test_signup_creates_account_and_never_returns_credentials(client: TestClient):
    body = signup(client)
    assert body["email"] == SIGNUP["email"]
    assert body["id"] == 1
    assert "password" not in body
    assert "hashed_password" not in body


def test_signup_duplicate_email_returns_409(client: TestClient):
    signup(client)
    response = client.post("/v1/auth/signup", json=SIGNUP)
    assert response.status_code == 409


def test_signup_rejects_short_password_with_422(client: TestClient):
    response = client.post("/v1/auth/signup", json={**SIGNUP, "password": "short"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "password"]


# --- login ------------------------------------------------------------------
def test_login_returns_bearer_token(client: TestClient):
    signup(client)
    response = login(client, SIGNUP["email"], SIGNUP["password"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_wrong_password_and_unknown_email_are_indistinguishable(
    client: TestClient,
):
    signup(client)
    wrong_pw = login(client, SIGNUP["email"], "not-the-password")
    unknown = login(client, "nobody@example.com", "whatever-pass")
    # Same status AND same detail — the response must not reveal whether
    # the email has an account (user enumeration).
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json()["detail"] == unknown.json()["detail"]


def test_login_deactivated_account_returns_401(client: TestClient):
    user = signup(client)
    client.patch(f"/v1/users/{user['id']}", json={"is_active": False})
    response = login(client, SIGNUP["email"], SIGNUP["password"])
    assert response.status_code == 401


# --- me ---------------------------------------------------------------------
def test_me_returns_the_token_owner(client: TestClient):
    headers = auth_header(client)
    response = client.get("/v1/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == SIGNUP["email"]


def test_me_without_token_returns_401(client: TestClient):
    response = client.get("/v1/auth/me")
    assert response.status_code == 401
    # RFC 6750: the challenge header tells clients which scheme to use.
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_me_with_garbage_token_returns_401(client: TestClient):
    response = client.get("/v1/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert response.status_code == 401


def test_token_stops_working_when_account_is_deactivated(client: TestClient):
    """A signed token is proof of PAST login — the dependency must re-check
    the account on every request, not just trust the signature."""
    headers = auth_header(client)
    user_id = client.get("/v1/auth/me", headers=headers).json()["id"]
    client.patch(f"/v1/users/{user_id}", json={"is_active": False})
    response = client.get("/v1/auth/me", headers=headers)
    assert response.status_code == 401


def test_token_stops_working_when_account_is_deleted(client: TestClient):
    headers = auth_header(client)
    user_id = client.get("/v1/auth/me", headers=headers).json()["id"]
    client.delete(f"/v1/users/{user_id}")
    response = client.get("/v1/auth/me", headers=headers)
    assert response.status_code == 401
