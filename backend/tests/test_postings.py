"""API tests for the postings resource (the async, auth-scoped stack).

TEACHING NOTE — these tests cross BOTH stacks on purpose: auth and users
run on the sync engine, postings on the async one, against one shared
database — exactly the production topology, minus postgres.
"""

from fastapi.testclient import TestClient

from tests.conftest import FakeGeoClient

POSTING = {
    "kind": "offer",
    "category": "goods",
    "title": "Espresso machine",
    "description": "Barista-grade, descaled monthly.",
    "tags": ["kitchen", "coffee"],
    "city": "Berlin",
}


def make_user(client: TestClient, email: str = "maya@example.com") -> dict:
    """Sign up and log in; returns the Authorization header."""
    response = client.post(
        "/v1/auth/signup",
        json={"email": email, "password": "correct-horse-battery"},
    )
    assert response.status_code == 201, response.text
    token = client.post(
        "/v1/auth/login", data={"username": email, "password": "correct-horse-battery"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_posting(client: TestClient, headers: dict, **overrides) -> dict:
    response = client.post("/v1/postings", json={**POSTING, **overrides}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# --- create -------------------------------------------------------------------
def test_create_requires_auth(client: TestClient):
    response = client.post("/v1/postings", json=POSTING)
    assert response.status_code == 401


def test_create_geocodes_and_assigns_owner(client: TestClient, geo: FakeGeoClient):
    headers = make_user(client)
    body = create_posting(client, headers)
    # The owner comes from the TOKEN, the coordinates from the geocoder —
    # neither was in the request body.
    assert body["owner_email"] == "maya@example.com"
    assert body["kind"] == "offer"
    assert body["category"] == "goods"
    assert body["tags"] == ["kitchen", "coffee"]
    assert (body["latitude"], body["longitude"]) == (1.25, 2.5)
    assert body["country"] == "Testland"
    assert body["is_active"] is True
    assert geo.geocode_calls == ["Berlin"]


def test_create_unknown_city_returns_422(client: TestClient):
    headers = make_user(client)
    response = client.post(
        "/v1/postings", json={**POSTING, "city": "Atlantis"}, headers=headers
    )
    assert response.status_code == 422
    assert "Atlantis" in response.json()["detail"]


def test_create_when_geocoder_is_down_returns_502(
    client: TestClient, geo: FakeGeoClient
):
    headers = make_user(client)
    geo.fail = True
    response = client.post("/v1/postings", json=POSTING, headers=headers)
    assert response.status_code == 502


def test_create_rejects_bad_kind_with_422(client: TestClient):
    headers = make_user(client)
    response = client.post(
        "/v1/postings", json={**POSTING, "kind": "wish"}, headers=headers
    )
    assert response.status_code == 422


# --- mine ----------------------------------------------------------------------
def test_mine_lists_only_my_postings_filtered_by_kind(client: TestClient):
    mine = make_user(client)
    others = make_user(client, email="leo@example.com")
    create_posting(client, mine, title="My offer")
    create_posting(client, mine, kind="need", category="service", title="My need")
    create_posting(client, others, title="Leo's offer")

    body = client.get("/v1/postings/mine", headers=mine).json()
    assert body["total"] == 2
    assert {p["title"] for p in body["items"]} == {"My offer", "My need"}

    body = client.get("/v1/postings/mine", params={"kind": "need"}, headers=mine).json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "My need"


def test_mine_includes_paused_postings(client: TestClient):
    headers = make_user(client)
    posting = create_posting(client, headers)
    client.patch(f"/v1/postings/{posting['id']}", json={"is_active": False}, headers=headers)
    body = client.get("/v1/postings/mine", headers=headers).json()
    assert body["total"] == 1
    assert body["items"][0]["is_active"] is False


# --- public read -----------------------------------------------------------------
def test_get_posting_is_public(client: TestClient):
    headers = make_user(client)
    posting = create_posting(client, headers)
    response = client.get(f"/v1/postings/{posting['id']}")  # no auth header
    assert response.status_code == 200
    assert response.json()["title"] == POSTING["title"]


def test_paused_posting_is_hidden_from_the_public(client: TestClient):
    headers = make_user(client)
    posting = create_posting(client, headers)
    client.patch(f"/v1/postings/{posting['id']}", json={"is_active": False}, headers=headers)
    # Same 404 as a nonexistent id: outsiders can't tell paused from gone.
    assert client.get(f"/v1/postings/{posting['id']}").status_code == 404


def test_get_missing_posting_returns_404(client: TestClient):
    assert client.get("/v1/postings/999").status_code == 404


# --- update / delete ---------------------------------------------------------------
def test_patch_title_does_not_regeocode(client: TestClient, geo: FakeGeoClient):
    headers = make_user(client)
    posting = create_posting(client, headers)
    response = client.patch(
        f"/v1/postings/{posting['id']}", json={"title": "Espresso maker"}, headers=headers
    )
    assert response.status_code == 200
    # One geocode from the create; the title-only PATCH must not add one.
    assert geo.geocode_calls == ["Berlin"]


def test_patch_city_regeocodes(client: TestClient, geo: FakeGeoClient):
    headers = make_user(client)
    posting = create_posting(client, headers)
    response = client.patch(
        f"/v1/postings/{posting['id']}", json={"city": "Lisbon"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["city"] == "Lisbon"
    assert geo.geocode_calls == ["Berlin", "Lisbon"]


def test_foreign_postings_cannot_be_modified_and_look_missing(client: TestClient):
    owner = make_user(client)
    intruder = make_user(client, email="intruder@example.com")
    posting = create_posting(client, owner)

    patched = client.patch(
        f"/v1/postings/{posting['id']}", json={"title": "Hijacked"}, headers=intruder
    )
    deleted = client.delete(f"/v1/postings/{posting['id']}", headers=intruder)
    # 404, not 403 — "not yours" must be indistinguishable from "not there".
    assert patched.status_code == 404
    assert deleted.status_code == 404
    # And the posting is untouched.
    assert client.get(f"/v1/postings/{posting['id']}").json()["title"] == POSTING["title"]


def test_delete_own_posting(client: TestClient):
    headers = make_user(client)
    posting = create_posting(client, headers)
    assert client.delete(f"/v1/postings/{posting['id']}", headers=headers).status_code == 204
    assert client.get(f"/v1/postings/{posting['id']}").status_code == 404


# --- cross-resource ------------------------------------------------------------------
def test_user_profile_shows_only_active_postings(client: TestClient):
    headers = make_user(client)
    create_posting(client, headers, title="Visible offer")
    paused = create_posting(client, headers, title="Paused offer")
    client.patch(f"/v1/postings/{paused['id']}", json={"is_active": False}, headers=headers)

    body = client.get("/v1/users/maya@example.com").json()
    assert [p["title"] for p in body["postings"]] == ["Visible offer"]


def test_meetup_conditions_gathers_weather_and_air(client: TestClient):
    headers = make_user(client)
    posting = create_posting(client, headers)
    response = client.get(f"/v1/postings/{posting['id']}/weather")
    assert response.status_code == 200
    body = response.json()
    assert body["posting_id"] == posting["id"]
    assert body["conditions"] == "partly cloudy"
    assert body["air_quality"] == "good"
    assert body["verdict"] == "Great day to meet and swap!"
