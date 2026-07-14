"""API tests for user location and the nearby-postings query.

TEACHING NOTE — geometry tests want REAL coordinates: the FakeGeoClient
maps Berlin/Potsdam/Hamburg to their true positions (see conftest), so
the assertions below check actual kilometers, not fixture artifacts.
Potsdam is ~27 km from Berlin; Hamburg ~255 km.
"""

import pytest
from fastapi.testclient import TestClient

from app.services.geo import haversine_km
from tests.conftest import FAKE_CITIES


def make_user(client: TestClient, email: str, city: str | None = None) -> dict:
    response = client.post(
        "/v1/auth/signup", json={"email": email, "password": "correct-horse-battery"}
    )
    assert response.status_code == 201, response.text
    token = client.post(
        "/v1/auth/login", data={"username": email, "password": "correct-horse-battery"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    if city is not None:
        response = client.put(
            "/v1/users/me/location", json={"city": city}, headers=headers
        )
        assert response.status_code == 200, response.text
    return headers


def create_posting(client: TestClient, headers: dict, city: str, **overrides) -> dict:
    payload = {
        "kind": "offer",
        "category": "goods",
        "title": f"Something in {city}",
        "city": city,
        **overrides,
    }
    response = client.post("/v1/postings", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# --- the haversine itself ------------------------------------------------------
def test_haversine_known_distance():
    berlin, hamburg = FAKE_CITIES["berlin"], FAKE_CITIES["hamburg"]
    distance = haversine_km(
        berlin.latitude, berlin.longitude, hamburg.latitude, hamburg.longitude
    )
    # The published Berlin–Hamburg great-circle distance is ~255 km.
    assert distance == pytest.approx(255, abs=5)
    # Zero distance to itself, symmetry both ways.
    assert haversine_km(52.5, 13.4, 52.5, 13.4) == 0
    assert distance == pytest.approx(
        haversine_km(hamburg.latitude, hamburg.longitude, berlin.latitude, berlin.longitude)
    )


# --- setting a location ----------------------------------------------------------
def test_set_location_geocodes_and_stores_canonical_city(client: TestClient):
    headers = make_user(client, "ada@example.com")
    response = client.put(
        "/v1/users/me/location", json={"city": "berlin"}, headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    # The geocoder's canonical spelling wins over the raw input...
    assert body["city"] == "Berlin"
    assert body["country"] == "Germany"
    # ...and the exact coordinates never appear in a response.
    assert "latitude" not in body
    assert "longitude" not in body


def test_set_location_unknown_city_returns_422(client: TestClient):
    headers = make_user(client, "ada@example.com")
    response = client.put(
        "/v1/users/me/location", json={"city": "Atlantis"}, headers=headers
    )
    assert response.status_code == 422


def test_set_location_requires_auth(client: TestClient):
    response = client.put("/v1/users/me/location", json={"city": "Berlin"})
    assert response.status_code == 401


# --- the nearby feed --------------------------------------------------------------
def seed_neighborhood(client: TestClient) -> dict:
    """A Berliner (the caller) surrounded by other people's postings."""
    me = make_user(client, "me@example.com", city="Berlin")
    berliner = make_user(client, "berliner@example.com", city="Berlin")
    potsdamer = make_user(client, "potsdamer@example.com", city="Potsdam")
    hamburger = make_user(client, "hamburger@example.com", city="Hamburg")
    create_posting(client, berliner, "Berlin")
    create_posting(client, potsdamer, "Potsdam")
    create_posting(client, potsdamer, "Potsdam", kind="need", category="service")
    create_posting(client, hamburger, "Hamburg")
    return me


def test_nearby_sorts_by_distance_and_respects_radius(client: TestClient):
    me = seed_neighborhood(client)
    body = client.get("/v1/postings/nearby", params={"radius_km": 50}, headers=me).json()
    # Berlin (~0 km) first, both Potsdam postings (~27 km) next;
    # Hamburg (~255 km) is outside the radius.
    assert body["total"] == 3
    cities = [p["city"] for p in body["items"]]
    assert cities[0] == "Berlin"
    assert set(cities[1:]) == {"Potsdam"}

    distances = [p["distance_km"] for p in body["items"]]
    assert distances == sorted(distances)
    assert distances[0] == pytest.approx(0, abs=0.1)
    assert distances[1] == pytest.approx(27, abs=2)


def test_nearby_wider_radius_includes_hamburg(client: TestClient):
    me = seed_neighborhood(client)
    body = client.get(
        "/v1/postings/nearby", params={"radius_km": 300}, headers=me
    ).json()
    assert body["total"] == 4
    assert body["items"][-1]["city"] == "Hamburg"
    assert body["items"][-1]["distance_km"] == pytest.approx(255, abs=5)


def test_nearby_excludes_my_own_postings(client: TestClient):
    me = seed_neighborhood(client)
    create_posting(client, me, "Berlin", title="My own sofa")
    body = client.get("/v1/postings/nearby", params={"radius_km": 50}, headers=me).json()
    assert all(p["owner_email"] != "me@example.com" for p in body["items"])
    assert body["total"] == 3


def test_nearby_excludes_paused_postings(client: TestClient):
    me = make_user(client, "me@example.com", city="Berlin")
    other = make_user(client, "other@example.com", city="Berlin")
    posting = create_posting(client, other, "Berlin")
    client.patch(
        f"/v1/postings/{posting['id']}", json={"is_active": False}, headers=other
    )
    body = client.get("/v1/postings/nearby", headers=me).json()
    assert body["total"] == 0


def test_nearby_filters_by_kind(client: TestClient):
    me = seed_neighborhood(client)
    body = client.get(
        "/v1/postings/nearby", params={"radius_km": 50, "kind": "need"}, headers=me
    ).json()
    assert body["total"] == 1
    assert body["items"][0]["kind"] == "need"


def test_nearby_without_location_returns_409(client: TestClient):
    headers = make_user(client, "nowhere@example.com")  # no city set
    response = client.get("/v1/postings/nearby", headers=headers)
    assert response.status_code == 409
    assert "location" in response.json()["detail"].lower()


def test_nearby_requires_auth(client: TestClient):
    assert client.get("/v1/postings/nearby").status_code == 401
