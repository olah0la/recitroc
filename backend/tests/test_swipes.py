"""API tests for the swipe deck, verdicts, and rewind."""

from fastapi.testclient import TestClient


def make_user(client: TestClient, email: str, city: str | None = "Berlin") -> dict:
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


def create_posting(client: TestClient, headers: dict, **overrides) -> dict:
    payload = {
        "kind": "offer",
        "category": "goods",
        "title": "Espresso machine",
        "city": "Berlin",
        **overrides,
    }
    response = client.post("/v1/postings", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def deck(client: TestClient, headers: dict, **params) -> list[dict]:
    response = client.get("/v1/swipes/deck", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


# --- the deck -----------------------------------------------------------------
def test_deck_requires_auth_and_location(client: TestClient):
    assert client.get("/v1/swipes/deck").status_code == 401
    homeless = make_user(client, "nowhere@example.com", city=None)
    assert client.get("/v1/swipes/deck", headers=homeless).status_code == 409


def test_deck_contains_nearby_offers_only(client: TestClient):
    me = make_user(client, "me@example.com")
    other = make_user(client, "other@example.com")
    create_posting(client, other, title="Nearby offer")
    create_posting(client, other, kind="need", category="service", title="A need")
    create_posting(client, other, title="Far offer", city="Hamburg")
    create_posting(client, me, title="My own offer")

    cards = deck(client, me, radius_km=50)
    # Needs, faraway postings and my own things never enter my deck.
    assert [c["title"] for c in cards] == ["Nearby offer"]
    assert cards[0]["distance_km"] >= 0


def test_deck_respects_limit(client: TestClient):
    me = make_user(client, "me@example.com")
    other = make_user(client, "other@example.com")
    for i in range(5):
        create_posting(client, other, title=f"Offer {i}")
    assert len(deck(client, me, limit=3)) == 3


# --- swiping --------------------------------------------------------------------
def test_swiped_postings_never_reappear_in_the_deck(client: TestClient):
    me = make_user(client, "me@example.com")
    other = make_user(client, "other@example.com")
    liked = create_posting(client, other, title="Liked")
    passed = create_posting(client, other, title="Passed")
    kept = create_posting(client, other, title="Untouched")

    for posting, direction in ((liked, "like"), (passed, "pass")):
        response = client.post(
            "/v1/swipes",
            json={"posting_id": posting["id"], "direction": direction},
            headers=me,
        )
        assert response.status_code == 201, response.text
        # No matching engine yet: the contract is there, the answer is no.
        assert response.json() == {"matched": False, "match_id": None}

    assert [c["id"] for c in deck(client, me)] == [kept["id"]]


def test_swipes_are_per_user(client: TestClient):
    me = make_user(client, "me@example.com")
    friend = make_user(client, "friend@example.com")
    other = make_user(client, "other@example.com")
    posting = create_posting(client, other)

    client.post(
        "/v1/swipes",
        json={"posting_id": posting["id"], "direction": "pass"},
        headers=me,
    )
    # My verdict empties MY deck, not my friend's.
    assert deck(client, me) == []
    assert [c["id"] for c in deck(client, friend)] == [posting["id"]]


def test_double_swipe_upserts_instead_of_failing(client: TestClient):
    me = make_user(client, "me@example.com")
    other = make_user(client, "other@example.com")
    posting = create_posting(client, other)

    for direction in ("like", "pass", "like"):
        response = client.post(
            "/v1/swipes",
            json={"posting_id": posting["id"], "direction": direction},
            headers=me,
        )
        assert response.status_code == 201, response.text

    # Exactly ONE verdict row exists: the first rewind succeeds, the
    # second finds nothing to withdraw.
    assert client.delete(f"/v1/swipes/{posting['id']}", headers=me).status_code == 204
    assert client.delete(f"/v1/swipes/{posting['id']}", headers=me).status_code == 404


def test_swipe_on_missing_paused_or_own_posting(client: TestClient):
    me = make_user(client, "me@example.com")
    other = make_user(client, "other@example.com")
    paused = create_posting(client, other, title="Paused")
    client.patch(
        f"/v1/postings/{paused['id']}", json={"is_active": False}, headers=other
    )
    mine = create_posting(client, me, title="Mine")

    missing = client.post(
        "/v1/swipes", json={"posting_id": 999, "direction": "like"}, headers=me
    )
    on_paused = client.post(
        "/v1/swipes", json={"posting_id": paused["id"], "direction": "like"}, headers=me
    )
    on_own = client.post(
        "/v1/swipes", json={"posting_id": mine["id"], "direction": "like"}, headers=me
    )
    assert missing.status_code == 404
    assert on_paused.status_code == 404  # paused == invisible, everywhere
    assert on_own.status_code == 409


def test_swipe_rejects_bad_direction_with_422(client: TestClient):
    me = make_user(client, "me@example.com")
    response = client.post(
        "/v1/swipes", json={"posting_id": 1, "direction": "sideways"}, headers=me
    )
    assert response.status_code == 422


# --- deck ranking (the scored deck, end to end) -----------------------------------
def test_deck_ranks_reciprocal_candidates_first(client: TestClient):
    """Same city, same freshness: the offer that overlaps my NEED and
    whose owner NEEDS my offer must beat a merely-nearby sofa."""
    me = make_user(client, "me@example.com")
    create_posting(client, me, kind="need", title="Mountain bike", tags=["bike"])
    create_posting(client, me, title="Guitar lessons", tags=["guitar", "music"])

    fit = make_user(client, "fit@example.com")
    create_posting(client, fit, title="Hardtail mountain bike", tags=["bike"])
    create_posting(
        client,
        fit,
        kind="need",
        category="service",
        title="Guitar teacher wanted",
        tags=["guitar"],
    )

    sofa = make_user(client, "sofa@example.com")
    create_posting(client, sofa, title="Old sofa", tags=["furniture"])

    cards = deck(client, me)
    # Only offers appear; the reciprocal one leads.
    assert [c["title"] for c in cards] == ["Hardtail mountain bike", "Old sofa"]


# --- rewind ---------------------------------------------------------------------
def test_rewind_returns_posting_to_the_deck(client: TestClient):
    me = make_user(client, "me@example.com")
    other = make_user(client, "other@example.com")
    posting = create_posting(client, other)

    client.post(
        "/v1/swipes",
        json={"posting_id": posting["id"], "direction": "pass"},
        headers=me,
    )
    assert deck(client, me) == []

    assert client.delete(f"/v1/swipes/{posting['id']}", headers=me).status_code == 204
    assert [c["id"] for c in deck(client, me)] == [posting["id"]]
