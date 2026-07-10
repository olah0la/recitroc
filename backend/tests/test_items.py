"""API tests for the items resource — focused on query-param filtering."""

from fastapi.testclient import TestClient


def seed(client: TestClient) -> tuple[dict, dict]:
    ada = client.post(
        "/v1/users", json={"email": "ada@example.com"}
    ).json()
    bob = client.post(
        "/v1/users", json={"email": "bob@example.com"}
    ).json()
    for owner, titles in ((ada, ["Vintage lamp", "Desk"]), (bob, ["Floor lamp"])):
        for title in titles:
            response = client.post(f"/v1/users/{owner['id']}/items", json={"title": title})
            assert response.status_code == 201
    return ada, bob


def test_create_item_for_missing_user_returns_404(client: TestClient):
    response = client.post("/v1/users/999/items", json={"title": "Lamp"})
    assert response.status_code == 404


def test_create_item_rejects_empty_title(client: TestClient):
    seed(client)
    response = client.post("/v1/users/1/items", json={"title": ""})
    assert response.status_code == 422


def test_list_items_unfiltered(client: TestClient):
    seed(client)
    body = client.get("/v1/items").json()
    assert body["total"] == 3


def test_list_items_filters_by_owner(client: TestClient):
    ada, _ = seed(client)
    body = client.get("/v1/items", params={"owner_id": ada["id"]}).json()
    assert body["total"] == 2
    assert all(item["owner_id"] == ada["id"] for item in body["items"])


def test_list_items_search_is_case_insensitive(client: TestClient):
    seed(client)
    body = client.get("/v1/items", params={"q": "LAMP"}).json()
    assert body["total"] == 2
    assert {item["title"] for item in body["items"]} == {"Vintage lamp", "Floor lamp"}


def test_filters_combine(client: TestClient):
    ada, _ = seed(client)
    body = client.get("/v1/items", params={"q": "lamp", "owner_id": ada["id"]}).json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Vintage lamp"


def test_update_item(client: TestClient):
    seed(client)
    response = client.patch("/v1/items/1", json={"description": "Still works!"})
    assert response.status_code == 200
    assert response.json()["description"] == "Still works!"
    assert response.json()["title"] == "Vintage lamp"
