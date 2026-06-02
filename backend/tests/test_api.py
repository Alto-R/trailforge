"""FastAPI endpoint contract tests via TestClient (设计 R1.3)."""
from __future__ import annotations


def test_health(client, engine):
    r = client.get("/health")
    assert r.status_code == 200
    j = r.json()
    assert j["model_loaded"] is True
    assert j["n_segments"] == engine.n_segments
    assert j["n_personas"] == 5


def test_personas(client):
    r = client.get("/personas")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 5
    assert {"id", "label", "description", "size", "default_prefs"} <= set(body[0])


def test_route_returns_candidates(client, junction_start):
    r = client.post("/route", json={
        "start": [junction_start["lng"], junction_start["lat"]],
        "preferences": {"challenge": 1.0}, "budget_km": 4.0, "n_routes": 4})
    assert r.status_code == 200
    j = r.json()
    assert 1 <= len(j["candidates"]) <= 4
    c = j["candidates"][0]
    assert c["geojson"]["type"] == "FeatureCollection"
    assert len(c["geojson"]["features"]) >= 1
    assert c["labels"]
    assert c["n_segments"] == len(c["segments"])
    assert len(j["start_snapped"]) == 2


def test_route_with_persona(client, start_point):
    r = client.post("/route", json={
        "start": [start_point["lng"], start_point["lat"]],
        "persona": start_point["persona"], "budget_km": 4.0})
    assert r.status_code == 200
    assert r.json()["prefs_used"]                  # persona defaults applied


def test_route_unknown_persona(client, start_point):
    r = client.post("/route", json={
        "start": [start_point["lng"], start_point["lat"]],
        "persona": "nope", "budget_km": 4.0})
    assert r.status_code == 422


def test_route_bad_budget(client, start_point):
    r = client.post("/route", json={
        "start": [start_point["lng"], start_point["lat"]],
        "budget_km": 0})
    assert r.status_code == 422


def test_route_malformed_start(client):
    r = client.post("/route", json={"start": [116.0], "budget_km": 4.0})
    assert r.status_code == 422


def test_trails(client):
    r = client.get("/trails")
    assert r.status_code == 200
    assert r.json()["type"] == "FeatureCollection"


def test_feedback(client):
    r = client.post("/feedback", json={"chosen_index": 0, "rating": 4, "comment": "ok"})
    assert r.status_code == 200
    assert r.json()["stored"] >= 1
