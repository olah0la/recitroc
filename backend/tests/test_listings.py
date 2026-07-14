"""API tests for the async listings resource.

TEACHING NOTE — these tests are plain `def` functions even though the
endpoints are `async def`: TestClient drives the app's event loop for us.
The FakeGeoClient (see conftest) replaces the real external service, so
the suite is fast, deterministic, and runs offline.
"""

from fastapi.testclient import TestClient
from tests.conftest import FakeGeoClient

PAYLOAD = {"title": "Espresso machine", "description": "Trade me!", "city": "Berlin"}


def create_listing(client: TestClient, **overrides) -> dict:
    response = client.post("/v1/listings", json={**PAYLOAD, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


def test_create_listing_stores_geocoded_coordinates(client: TestClient):
    body = create_listing(client)
    # The client sent only a city name; coordinates came from the
    # (fake) geocoding service.
    assert body["country"] == "Testland"
    assert body["latitude"] == 1.25
    assert body["longitude"] == 2.5


def test_create_listing_unknown_city_returns_422(client: TestClient):
    response = client.post("/v1/listings", json={**PAYLOAD, "city": "Atlantis"})
    assert response.status_code == 422
    assert "Atlantis" in response.json()["detail"]


def test_create_listing_provider_outage_returns_502(
    client: TestClient, geo: FakeGeoClient
):
    geo.fail = True
    response = client.post("/v1/listings", json=PAYLOAD)
    # Upstream failure surfaces as 502 Bad Gateway, never a raw 500.
    assert response.status_code == 502


def test_list_listings_filters_by_city_case_insensitively(client: TestClient):
    create_listing(client, city="Berlin")
    create_listing(client, city="Nairobi", title="Bicycle")

    body = client.get("/v1/listings", params={"city": "nairobi"}).json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Bicycle"


def test_patch_title_does_not_re_geocode(client: TestClient, geo: FakeGeoClient):
    listing = create_listing(client)
    assert geo.geocode_calls == ["Berlin"]

    response = client.patch(f"/v1/listings/{listing['id']}", json={"title": "Moka pot"})
    assert response.status_code == 200
    # Only the city triggers geocoding; a title change must not call the
    # external service (that's a real bill and real latency in prod).
    assert geo.geocode_calls == ["Berlin"]


def test_patch_city_re_geocodes(client: TestClient, geo: FakeGeoClient):
    listing = create_listing(client)
    response = client.patch(f"/v1/listings/{listing['id']}", json={"city": "Nairobi"})
    assert response.status_code == 200
    assert geo.geocode_calls == ["Berlin", "Nairobi"]
    assert response.json()["city"] == "Nairobi"


def test_meetup_conditions_combines_weather_and_air_quality(client: TestClient):
    listing = create_listing(client)
    response = client.get(f"/v1/listings/{listing['id']}/weather")
    assert response.status_code == 200
    body = response.json()
    # Fields from BOTH concurrent external calls, merged into one response.
    assert body["conditions"] == "partly cloudy"  # weather API (code 2)
    assert body["air_quality"] == "good"  # air-quality API (AQI 15)
    assert body["verdict"] == "Great day to meet and swap!"


def test_meetup_conditions_provider_outage_returns_502(
    client: TestClient, geo: FakeGeoClient
):
    listing = create_listing(client)
    geo.fail = True
    assert client.get(f"/v1/listings/{listing['id']}/weather").status_code == 502


def test_get_missing_listing_returns_404(client: TestClient):
    assert client.get("/v1/listings/999").status_code == 404


def test_delete_listing(client: TestClient):
    listing = create_listing(client)
    assert client.delete(f"/v1/listings/{listing['id']}").status_code == 204
    assert client.get(f"/v1/listings/{listing['id']}").status_code == 404
