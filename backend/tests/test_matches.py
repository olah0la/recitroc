"""API tests for the matching engine (mutual likes → matches)."""

from fastapi.testclient import TestClient


def make_user(client: TestClient, email: str) -> dict:
    response = client.post(
        "/v1/auth/signup", json={"email": email, "password": "correct-horse-battery"}
    )
    assert response.status_code == 201, response.text
    token = client.post(
        "/v1/auth/login", data={"username": email, "password": "correct-horse-battery"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    client.put("/v1/users/me/location", json={"city": "Berlin"}, headers=headers)
    return headers


def create_posting(client: TestClient, headers: dict, title: str, **overrides) -> dict:
    payload = {
        "kind": "offer",
        "category": "goods",
        "title": title,
        "city": "Berlin",
        **overrides,
    }
    response = client.post("/v1/postings", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def swipe(client: TestClient, headers: dict, posting_id: int, direction: str) -> dict:
    response = client.post(
        "/v1/swipes",
        json={"posting_id": posting_id, "direction": direction},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def mutual_like_setup(client: TestClient) -> tuple[dict, dict, dict, dict]:
    """Ada and Bob, one offer each. Returns (ada, bob, ada_posting, bob_posting)."""
    ada = make_user(client, "ada@example.com")
    bob = make_user(client, "bob@example.com")
    ada_posting = create_posting(client, ada, "Ada's camera")
    bob_posting = create_posting(client, bob, "Bob's bike")
    return ada, bob, ada_posting, bob_posting


# --- match creation ---------------------------------------------------------------
def test_mutual_like_creates_exactly_one_match(client: TestClient):
    ada, bob, ada_posting, bob_posting = mutual_like_setup(client)

    # First like: one-sided, no match yet.
    first = swipe(client, ada, bob_posting["id"], "like")
    assert first == {"matched": False, "match_id": None}

    # The reciprocal like completes the pair.
    second = swipe(client, bob, ada_posting["id"], "like")
    assert second["matched"] is True
    assert second["match_id"] is not None

    # Both users see the SAME single match, each from their own side.
    ada_view = client.get("/v1/matches", headers=ada).json()
    bob_view = client.get("/v1/matches", headers=bob).json()
    assert ada_view["total"] == bob_view["total"] == 1
    assert ada_view["items"][0]["id"] == bob_view["items"][0]["id"]

    ada_match = ada_view["items"][0]
    assert ada_match["status"] == "active"
    assert ada_match["partner"]["email"] == "bob@example.com"
    assert ada_match["my_posting"]["title"] == "Ada's camera"
    assert ada_match["their_posting"]["title"] == "Bob's bike"

    bob_match = bob_view["items"][0]
    assert bob_match["partner"]["email"] == "ada@example.com"
    assert bob_match["my_posting"]["title"] == "Bob's bike"
    assert bob_match["their_posting"]["title"] == "Ada's camera"


def test_repeat_likes_do_not_duplicate_or_recelebrate(client: TestClient):
    ada, bob, ada_posting, bob_posting = mutual_like_setup(client)
    swipe(client, ada, bob_posting["id"], "like")
    swipe(client, bob, ada_posting["id"], "like")

    # Bob likes ANOTHER posting of Ada's: the pair is already matched.
    ada_second = create_posting(client, ada, "Ada's guitar")
    result = swipe(client, bob, ada_second["id"], "like")
    assert result == {"matched": False, "match_id": None}

    assert client.get("/v1/matches", headers=ada).json()["total"] == 1


def test_pass_never_matches(client: TestClient):
    ada, bob, ada_posting, bob_posting = mutual_like_setup(client)
    swipe(client, ada, bob_posting["id"], "like")
    result = swipe(client, bob, ada_posting["id"], "pass")
    assert result == {"matched": False, "match_id": None}
    assert client.get("/v1/matches", headers=bob).json()["total"] == 0


def test_one_sided_likes_never_match(client: TestClient):
    ada, bob, _, bob_posting = mutual_like_setup(client)
    result = swipe(client, ada, bob_posting["id"], "like")
    assert result["matched"] is False
    assert client.get("/v1/matches", headers=ada).json()["total"] == 0


def test_matches_require_auth(client: TestClient):
    assert client.get("/v1/matches").status_code == 401


def test_match_survives_posting_deletion(client: TestClient):
    """The FK is SET NULL: deleting a posting keeps the match alive."""
    ada, bob, ada_posting, bob_posting = mutual_like_setup(client)
    swipe(client, ada, bob_posting["id"], "like")
    swipe(client, bob, ada_posting["id"], "like")

    assert (
        client.delete(f"/v1/postings/{bob_posting['id']}", headers=bob).status_code
        == 204
    )
    body = client.get("/v1/matches", headers=ada).json()
    assert body["total"] == 1
    assert body["items"][0]["their_posting"] is None
    assert body["items"][0]["my_posting"]["title"] == "Ada's camera"
