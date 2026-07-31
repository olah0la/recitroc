"""API tests for match-scoped messaging (RT-6)."""

from fastapi.testclient import TestClient

from tests.test_matches import create_posting, make_user, mutual_like_setup, swipe


def make_match(client: TestClient) -> tuple[dict, dict, int]:
    """Ada and Bob, mutually matched. Returns (ada, bob, match_id)."""
    ada, bob, ada_posting, bob_posting = mutual_like_setup(client)
    swipe(client, ada, bob_posting["id"], "like")
    result = swipe(client, bob, ada_posting["id"], "like")
    assert result["matched"] is True
    return ada, bob, result["match_id"]


def send(client: TestClient, headers: dict, match_id: int, body: str) -> dict:
    response = client.post(
        f"/v1/matches/{match_id}/messages", json={"body": body}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


# --- the conversation -------------------------------------------------------------
def test_send_and_fetch_roundtrip(client: TestClient):
    ada, bob, match_id = make_match(client)

    sent = send(client, ada, match_id, "Hi! Still trading the bike?")
    assert sent["match_id"] == match_id
    assert sent["sender_email"] == "ada@example.com"
    assert sent["read_at"] is None

    send(client, bob, match_id, "Yes! Your camera looks great.")

    thread = client.get(f"/v1/matches/{match_id}/messages", headers=ada).json()
    assert [m["body"] for m in thread] == [
        "Hi! Still trading the bike?",
        "Yes! Your camera looks great.",
    ]
    # Oldest first, ids ascending — the polling contract.
    assert thread[0]["id"] < thread[1]["id"]


def test_after_id_returns_only_newer_messages(client: TestClient):
    ada, bob, match_id = make_match(client)
    first = send(client, ada, match_id, "one")
    send(client, bob, match_id, "two")
    send(client, ada, match_id, "three")

    newer = client.get(
        f"/v1/matches/{match_id}/messages?after_id={first['id']}", headers=ada
    ).json()
    assert [m["body"] for m in newer] == ["two", "three"]

    # Cursor at the tail: nothing new — the common polling case.
    tail = newer[-1]["id"]
    assert (
        client.get(
            f"/v1/matches/{match_id}/messages?after_id={tail}", headers=ada
        ).json()
        == []
    )


# --- read state -------------------------------------------------------------------
def test_mark_read_counts_and_idempotency(client: TestClient):
    ada, bob, match_id = make_match(client)
    send(client, ada, match_id, "hello")
    send(client, ada, match_id, "you there?")
    send(client, bob, match_id, "here!")

    # Bob has two unread (Ada's); his own message never counts.
    bob_view = client.get("/v1/matches", headers=bob).json()["items"][0]
    assert bob_view["unread_count"] == 2
    assert bob_view["last_message"]["body"] == "here!"

    marked = client.post(f"/v1/matches/{match_id}/read", headers=bob).json()
    assert marked == {"marked_read": 2}

    # Idempotent: nothing left to mark.
    assert client.post(f"/v1/matches/{match_id}/read", headers=bob).json() == {
        "marked_read": 0
    }
    assert (
        client.get("/v1/matches", headers=bob).json()["items"][0]["unread_count"] == 0
    )

    # Ada (the sender) now sees her messages as read; Bob's to her is not.
    thread = client.get(f"/v1/matches/{match_id}/messages", headers=ada).json()
    assert thread[0]["read_at"] is not None
    assert thread[2]["read_at"] is None
    assert (
        client.get("/v1/matches", headers=ada).json()["items"][0]["unread_count"] == 1
    )


def test_match_list_preview_without_messages(client: TestClient):
    ada, _, _ = make_match(client)
    view = client.get("/v1/matches", headers=ada).json()["items"][0]
    assert view["last_message"] is None
    assert view["unread_count"] == 0


# --- authorization ----------------------------------------------------------------
def test_non_participants_get_403_everywhere(client: TestClient):
    _, _, match_id = make_match(client)
    eve = make_user(client, "eve@example.com")

    assert (
        client.get(f"/v1/matches/{match_id}/messages", headers=eve).status_code == 403
    )
    assert (
        client.post(
            f"/v1/matches/{match_id}/messages", json={"body": "hi"}, headers=eve
        ).status_code
        == 403
    )
    assert client.post(f"/v1/matches/{match_id}/read", headers=eve).status_code == 403


def test_unknown_match_is_404(client: TestClient):
    ada = make_user(client, "ada@example.com")
    assert client.get("/v1/matches/999/messages", headers=ada).status_code == 404


def test_messages_require_auth(client: TestClient):
    assert client.get("/v1/matches/1/messages").status_code == 401
    assert client.post("/v1/matches/1/messages", json={"body": "x"}).status_code == 401
    assert client.post("/v1/matches/1/read").status_code == 401


# --- body validation --------------------------------------------------------------
def test_body_validation(client: TestClient):
    ada, bob, match_id = make_match(client)

    for bad in ["", "   ", "x" * 2001]:
        response = client.post(
            f"/v1/matches/{match_id}/messages", json={"body": bad}, headers=ada
        )
        assert response.status_code == 422, f"body {bad!r} should be rejected"

    # Whitespace is trimmed, not stored.
    sent = send(client, ada, match_id, "  trimmed  ")
    assert sent["body"] == "trimmed"
