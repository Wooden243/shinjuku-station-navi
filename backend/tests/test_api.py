from fastapi.testclient import TestClient


def test_health_reports_real_open_data(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["data_loaded"] is True
    assert payload["data_mode"] == "open-data"
    assert payload["node_count"] == 2506
    assert payload["link_count"] == 2647
    assert payload["gate_count"] == 31
    assert payload["exit_count"] == 35
    assert payload["source"]["crs"] == "EPSG:4326"


def test_places_are_limited_to_gates_and_exits(client: TestClient) -> None:
    gates = client.get("/api/gates")
    exits = client.get("/api/exits")
    assert gates.status_code == 200
    assert exits.status_code == 200
    assert all(place["type"] == "gate" for place in gates.json())
    assert all(place["type"] == "exit" for place in exits.json())
    assert all("トイレ" not in place["name"] for place in exits.json())


def test_real_route_is_split_by_floor(client: TestClient) -> None:
    response = client.post(
        "/api/routes",
        json={
            "start_gate_id": "gate-1759781",
            "destination_exit_id": "exit-1760728",
            "preferences": {"avoid_stairs": False},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["distance_meters"] > 0
    assert payload["floors"] == ["B1", "1F"]
    assert payload["floor_transitions"][0]["type"] == "stairs"
    assert payload["route_by_floor"]["B1"]["type"] == "FeatureCollection"
    assert payload["data_source"]["data_mode"] == "open-data"
    assert payload["data_source"]["crs"] == "EPSG:4326"
    assert len(payload["instructions"]) < 12


def test_floor_map_uses_requested_floor(client: TestClient) -> None:
    response = client.get("/api/floor-map", params={"floor": "B1"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "FeatureCollection"
    assert payload["features"]
    assert all(feature["properties"]["floor"] == "B1" for feature in payload["features"])


def test_unknown_place_is_not_silently_accepted(client: TestClient) -> None:
    response = client.post(
        "/api/routes",
        json={
            "start_gate_id": "missing",
            "destination_exit_id": "exit-1760728",
        },
    )
    assert response.status_code == 404


def test_unknown_floor_is_not_an_empty_success(client: TestClient) -> None:
    response = client.get("/api/network", params={"floor": "UNKNOWN"})
    assert response.status_code == 404

