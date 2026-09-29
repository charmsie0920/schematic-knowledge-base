# backend/tests/test_runs_api.py
"""End to end: start a fake run, read it back over SSE. Requires `docker compose up -d`."""

from fastapi.testclient import TestClient

from app.events.schema import Event, ItemStateChanged, RunDone, RunStarted, parse_event


def read_events(client: TestClient, url: str) -> list[Event]:
    events: list[Event] = []
    with client.stream("GET", url) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        for line in response.iter_lines():
            if line.startswith("data: "):
                events.append(parse_event(line.removeprefix("data: ")))
    return events


def test_fake_run_streams_every_event_over_sse(client: TestClient) -> None:
    start = client.post("/runs/fake", json={"total_items": 25, "speed": 1000, "seed": 7})
    assert start.status_code == 202, start.text
    body = start.json()
    assert body["events_url"].endswith(f"/runs/{body['run_id']}/events")

    # The run waits for this subscriber, so no event is lost; the stream ends at run.done.
    events = read_events(client, body["events_url"])

    assert isinstance(events[0], RunStarted)
    assert isinstance(events[-1], RunDone)
    assert events[-1].indexed + events[-1].failed == 25
    assert {e.run_id for e in events} == {body["run_id"]}
    items = {e.item_id for e in events if isinstance(e, ItemStateChanged)}
    assert len(items) == 25


def test_invalid_config_is_rejected(client: TestClient) -> None:
    response = client.post("/runs/fake", json={"total_items": 0})

    assert response.status_code == 422


def test_malformed_run_id_is_rejected(client: TestClient) -> None:
    response = client.get("/runs/bad*id/events")

    assert response.status_code == 422
