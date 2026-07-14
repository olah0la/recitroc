"""API tests for the items resource — focused on query-param filtering."""

from fastapi.testclient import TestClient

ADA = "ada@example.com"
BOB = "bob@example.com"


def seed(client: TestClient) -> None:
    for email in (ADA, BOB):
        response = client.post(
            "/v1/users", json={"email": email, "password": "correct-horse-battery"}
        )
        assert response.status_code == 201
    for owner, titles in ((ADA, ["Vintage lamp", "Desk"]), (BOB, ["Floor lamp"])):
        for title in titles:
            response = client.post(f"/v1/users/{owner}/items", json={"title": title})
            assert response.status_code == 201


def test_create_item_for_missing_user_returns_404(client: TestClient):
    response = client.post("/v1/users/nobody@example.com/items", json={"title": "Lamp"})
    assert response.status_code == 404


def test_create_item_rejects_empty_title(client: TestClient):
    seed(client)
    response = client.post(f"/v1/users/{ADA}/items", json={"title": ""})
    assert response.status_code == 422


def test_list_items_unfiltered(client: TestClient):
    seed(client)
    body = client.get("/v1/items").json()
    assert body["total"] == 3


def test_list_items_filters_by_owner(client: TestClient):
    seed(client)
    body = client.get("/v1/items", params={"owner_email": ADA}).json()
    assert body["total"] == 2
    assert all(item["owner_email"] == ADA for item in body["items"])


def test_list_items_search_is_case_insensitive(client: TestClient):
    seed(client)
    body = client.get("/v1/items", params={"q": "LAMP"}).json()
    assert body["total"] == 2
    assert {item["title"] for item in body["items"]} == {"Vintage lamp", "Floor lamp"}


def test_filters_combine(client: TestClient):
    seed(client)
    body = client.get("/v1/items", params={"q": "lamp", "owner_email": ADA}).json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Vintage lamp"


def test_update_item(client: TestClient):
    seed(client)
    response = client.patch("/v1/items/1", json={"description": "Still works!"})
    assert response.status_code == 200
    assert response.json()["description"] == "Still works!"
    assert response.json()["title"] == "Vintage lamp"
