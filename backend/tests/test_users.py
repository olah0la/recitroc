"""API tests for the users resource.

TEACHING NOTE — test through the HTTP layer when you can: these tests
exercise routing, validation, serialization, status codes AND the CRUD
layer in one go, and they only depend on the public contract — you can
refactor internals freely without touching them.
"""

from fastapi.testclient import TestClient

PAYLOAD = {"email": "ada@example.com", "full_name": "Ada Lovelace"}


def create_user(client: TestClient, **overrides) -> dict:
    response = client.post("/v1/users", json={**PAYLOAD, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


def test_create_user_returns_201_with_server_generated_fields(client: TestClient):
    body = create_user(client)
    assert body["email"] == PAYLOAD["email"]
    assert body["is_active"] is True
    # Server-generated fields must exist even though the client never sent them.
    assert body["id"] == 1
    assert "created_at" in body


def test_create_user_rejects_invalid_email_with_422(client: TestClient):
    response = client.post("/v1/users", json={"email": "not-an-email"})
    # 422 = FastAPI/Pydantic validation failure; the body pinpoints the field.
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "email"]


def test_create_user_duplicate_email_returns_409(client: TestClient):
    create_user(client)
    response = client.post("/v1/users", json=PAYLOAD)
    assert response.status_code == 409


def test_list_users_paginates(client: TestClient):
    for i in range(3):
        create_user(client, email=f"user{i}@example.com")

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
    client.post(f"/v1/users/{user['id']}/items", json={"title": "Lamp"})

    response = client.get(f"/v1/users/{user['id']}")
    assert response.status_code == 200
    body = response.json()
    assert [item["title"] for item in body["items"]] == ["Lamp"]


def test_get_missing_user_returns_404(client: TestClient):
    response = client.get("/v1/users/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_patch_updates_only_sent_fields(client: TestClient):
    user = create_user(client)
    response = client.patch(f"/v1/users/{user['id']}", json={"full_name": "Ada L."})
    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Ada L."
    # PATCH semantics: the email was not in the payload, so it is untouched.
    assert body["email"] == PAYLOAD["email"]


def test_delete_user_returns_204_and_cascades_to_items(client: TestClient):
    user = create_user(client)
    item = client.post(f"/v1/users/{user['id']}/items", json={"title": "Lamp"}).json()

    response = client.delete(f"/v1/users/{user['id']}")
    assert response.status_code == 204

    assert client.get(f"/v1/users/{user['id']}").status_code == 404
    # The ORM cascade removed the orphaned item as well.
    assert client.get(f"/v1/items/{item['id']}").status_code == 404
