"""API tests for the users resource.

TEACHING NOTE — test through the HTTP layer when you can: these tests
exercise routing, validation, serialization, status codes AND the CRUD
layer in one go, and they only depend on the public contract — you can
refactor internals freely without touching them.
"""

from fastapi.testclient import TestClient

PAYLOAD = {
    "email": "ada@example.com",
    "username": "ada_l",
    "first_name": "Ada",
    "last_name": "Lovelace",
    "password": "correct-horse-battery",
}


def create_user(client: TestClient, **overrides) -> dict:
    response = client.post("/v1/users", json={**PAYLOAD, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


def test_create_user_returns_201_with_server_generated_fields(client: TestClient):
    body = create_user(client)
    assert body["email"] == PAYLOAD["email"]
    assert body["username"] == PAYLOAD["username"]
    assert body["first_name"] == "Ada"
    assert body["last_name"] == "Lovelace"
    assert body["is_active"] is True
    # Server-generated fields must exist even though the client never sent them.
    assert "created_at" in body
    # response_model=UserRead filters the output: credential material can
    # never leak, in ANY form.
    assert "password" not in body
    assert "hashed_password" not in body


def test_create_user_rejects_invalid_email_with_422(client: TestClient):
    response = client.post("/v1/users", json={"email": "not-an-email"})
    # 422 = FastAPI/Pydantic validation failure; the body pinpoints the field.
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "email"]


def test_create_user_duplicate_email_returns_409(client: TestClient):
    create_user(client)
    response = client.post("/v1/users", json=PAYLOAD)
    assert response.status_code == 409


def test_username_is_optional_but_unique(client: TestClient):
    # Two users with NO username coexist fine: SQL unique constraints
    # treat NULLs as distinct values.
    create_user(client, email="a@example.com", username=None)
    create_user(client, email="b@example.com", username=None)
    # But a TAKEN username is a 409, same as a taken email.
    create_user(client, email="c@example.com", username="taken")
    response = client.post(
        "/v1/users",
        json={**PAYLOAD, "email": "d@example.com", "username": "taken"},
    )
    assert response.status_code == 409


def test_list_users_paginates(client: TestClient):
    for i in range(3):
        create_user(client, email=f"user{i}@example.com", username=f"user{i}")

    response = client.get("/v1/users", params={"limit": 2, "offset": 0})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2

    response = client.get("/v1/users", params={"limit": 2, "offset": 2})
    assert len(response.json()["items"]) == 1


def test_list_users_rejects_out_of_range_limit(client: TestClient):
    # limit is capped at 100 by the Pagination dependency (Query(le=100)).
    response = client.get("/v1/users", params={"limit": 5000})
    assert response.status_code == 422


def test_get_user_includes_items(client: TestClient):
    user = create_user(client)
    client.post(f"/v1/users/{user['email']}/items", json={"title": "Lamp"})

    response = client.get(f"/v1/users/{user['email']}")
    assert response.status_code == 200
    body = response.json()
    assert [item["title"] for item in body["items"]] == ["Lamp"]


def test_get_missing_user_returns_404(client: TestClient):
    response = client.get("/v1/users/nobody@example.com")
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_get_user_with_malformed_email_returns_422(client: TestClient):
    # The path param is typed EmailStr: /users/42 is not a valid resource
    # identifier anymore and never reaches the handler.
    response = client.get("/v1/users/42")
    assert response.status_code == 422


def test_patch_updates_only_sent_fields(client: TestClient):
    user = create_user(client)
    response = client.patch(
        f"/v1/users/{user['email']}", json={"first_name": "Adaline"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["first_name"] == "Adaline"
    # PATCH semantics: fields not in the payload are untouched.
    assert body["last_name"] == PAYLOAD["last_name"]
    assert body["email"] == PAYLOAD["email"]


def test_patch_email_rekeys_the_resource(client: TestClient):
    """Changing the email changes the PRIMARY KEY — and thus the URL."""
    user = create_user(client)
    response = client.patch(
        f"/v1/users/{user['email']}", json={"email": "ada@newdomain.org"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == "ada@newdomain.org"
    # The resource now lives at the new identifier; the old one is gone.
    assert client.get("/v1/users/ada@newdomain.org").status_code == 200
    assert client.get(f"/v1/users/{PAYLOAD['email']}").status_code == 404


def test_patch_to_taken_username_returns_409(client: TestClient):
    create_user(client)
    other = create_user(client, email="other@example.com", username="other")
    response = client.patch(
        f"/v1/users/{other['email']}", json={"username": PAYLOAD["username"]}
    )
    assert response.status_code == 409


def test_delete_user_returns_204_and_cascades_to_items(client: TestClient):
    user = create_user(client)
    item = client.post(
        f"/v1/users/{user['email']}/items", json={"title": "Lamp"}
    ).json()

    response = client.delete(f"/v1/users/{user['email']}")
    assert response.status_code == 204

    assert client.get(f"/v1/users/{user['email']}").status_code == 404
    # The ORM cascade removed the orphaned item as well.
    assert client.get(f"/v1/items/{item['id']}").status_code == 404
