from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient


def mapping_payload(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "client_submission_id": str(uuid4()),
        "category": "shop",
        "name": "テスト店舗",
        "description": "改札前にある店舗を現地で確認しました",
        "floor": "B1",
        "lon": 139.7006,
        "lat": 35.691,
        "source_method": "2026-07-28に現地の表示を目視確認",
        "supplemental": None,
    }
    payload.update(updates)
    return payload


def admin_headers() -> dict[str, str]:
    return {"X-Admin-Key": "test-admin-key"}


def test_health_reports_real_open_data_and_database(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["data_loaded"] is True
    assert payload["database_ready"] is True
    assert payload["data_mode"] == "open-data"
    assert payload["dataset_version"] == "fc3466270c08593a-map-62"
    assert payload["node_count"] == 2506
    assert payload["link_count"] == 2647
    assert payload["gate_count"] == 31
    assert payload["exit_count"] == 35
    assert payload["facility_count"] == 1188
    assert payload["source"]["crs"] == "EPSG:4326"


def test_exit_detail_exposes_unknowns_and_provenance(client: TestClient) -> None:
    response = client.get("/api/exits/exit-1760734")
    assert response.status_code == 200
    payload = response.json()
    assert payload["exit_number"] == "10"
    assert payload["official_name"] == "10出口"
    assert payload["floor"] == "1F"
    assert payload["road_or_direction"] is None
    assert payload["accessibility"] is None
    assert payload["available_hours"] is None
    assert payload["verification_status"] == "not-verified"
    assert payload["provenance"]["road_or_direction"] == "no-data"
    assert payload["provenance"]["nearby_landmarks"] == "derived-open-data"
    assert payload["source"]["provider"] == "東京都都市整備局"
    assert payload["data_updated_at"] == "2023-02-20T18:55:00Z"


def test_facilities_are_real_processed_open_data(client: TestClient) -> None:
    response = client.get(
        "/api/facilities", params={"floor": "B1", "category": "atm"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload
    assert all(item["category"] == "atm" for item in payload)
    assert all(item["floor"] == "B1" for item in payload)
    assert all(item["is_sample"] is False for item in payload)
    assert all(item["source"]["provider"] == "東京都都市整備局" for item in payload)


def test_places_are_limited_to_gates_and_exits(client: TestClient) -> None:
    gates = client.get("/api/gates")
    exits = client.get("/api/exits")
    assert gates.status_code == 200
    assert exits.status_code == 200
    assert all(place["type"] == "gate" for place in gates.json())
    assert all(place["type"] == "exit" for place in exits.json())
    assert all("トイレ" not in place["name"] for place in exits.json())


def test_real_route_is_split_by_floor_and_ordered(client: TestClient) -> None:
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
    sequence = [
        item["properties"]["sequence"]
        for item in payload["route_by_floor"]["B1"]["features"]
    ]
    assert sequence == sorted(sequence)
    assert payload["data_source"]["data_mode"] == "open-data"
    assert payload["data_source"]["crs"] == "EPSG:4326"
    assert payload["data_source"]["dataset_version"]
    assert len(payload["instructions"]) < 20


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


def test_offline_bundle_contains_all_navigation_data(client: TestClient) -> None:
    response = client.get("/api/offline-bundle")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["nodes"]) == 2506
    assert payload["edges"]
    assert len(payload["places"]) == 66
    assert len(payload["facilities"]) == 1188
    assert "B1" in payload["networks_by_floor"]
    assert "B1" in payload["floor_maps_by_floor"]
    assert payload["walking_speed_m_per_minute"] == 80
    assert payload["route_spec_version"] == "1.0"


def test_mapping_submission_requires_review_before_publication(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/mapping-submissions",
        headers={"X-Client-Id": "client-review-0001"},
        json=mapping_payload(),
    )
    assert created.status_code == 201
    assert created.json()["status"] == "pending"
    assert client.get("/api/mapping-submissions/public").json() == []

    unauthorized = client.get("/api/admin/mapping-submissions")
    assert unauthorized.status_code == 401
    listed = client.get("/api/admin/mapping-submissions", headers=admin_headers())
    assert listed.status_code == 200
    submission_id = listed.json()[0]["id"]
    approved = client.patch(
        f"/api/admin/mapping-submissions/{submission_id}",
        headers=admin_headers(),
        json={"status": "approved", "review_note": "根拠を確認して承認"},
    )
    assert approved.status_code == 200
    assert approved.json()["reviewed_by"] == "local-development-admin"
    public = client.get("/api/mapping-submissions/public").json()
    assert len(public) == 1
    assert public[0]["review_note"] == ""
    assert public[0]["reviewed_by"] is None


def test_duplicate_mapping_increments_support_once_per_client(
    client: TestClient,
) -> None:
    first_payload = mapping_payload(category="exit_note", name="南側案内")
    first = client.post(
        "/api/mapping-submissions",
        headers={"X-Client-Id": "client-duplicate-01"},
        json=first_payload,
    )
    second = client.post(
        "/api/mapping-submissions",
        headers={"X-Client-Id": "client-duplicate-02"},
        json=mapping_payload(
            category="exit_note",
            name="南側案内",
            description=first_payload["description"],
            lon=139.70061,
        ),
    )
    repeat = client.post(
        "/api/mapping-submissions",
        headers={"X-Client-Id": "client-duplicate-02"},
        json=mapping_payload(
            category="exit_note",
            name="南側案内",
            description=first_payload["description"],
            lon=139.70061,
        ),
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["support_count"] == 2
    assert repeat.json()["support_count"] == 2


def test_client_submission_id_makes_offline_sync_idempotent(
    client: TestClient,
) -> None:
    payload = mapping_payload(client_submission_id="offline-stable-id-0001")
    first = client.post(
        "/api/mapping-submissions",
        headers={"X-Client-Id": "client-offline-sync"},
        json=payload,
    )
    second = client.post(
        "/api/mapping-submissions",
        headers={"X-Client-Id": "client-offline-sync"},
        json=payload,
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["support_count"] == 1


def test_mapping_validation_rejects_html_and_outside_coordinates(
    client: TestClient,
) -> None:
    html_response = client.post(
        "/api/mapping-submissions",
        headers={"X-Client-Id": "client-validation-html"},
        json=mapping_payload(description="<script>alert(1)</script>"),
    )
    coordinate_response = client.post(
        "/api/mapping-submissions",
        headers={"X-Client-Id": "client-validation-coord"},
        json=mapping_payload(lon=0),
    )
    assert html_response.status_code == 422
    assert coordinate_response.status_code == 422


def test_mapping_rate_limit_is_enforced_server_side(client: TestClient) -> None:
    headers = {"X-Client-Id": "client-rate-limit"}
    for index in range(6):
        response = client.post(
            "/api/mapping-submissions",
            headers=headers,
            json=mapping_payload(
                name=f"別地点{index}",
                lon=139.699 + index * 0.0001,
            ),
        )
        assert response.status_code == 201
    blocked = client.post(
        "/api/mapping-submissions",
        headers=headers,
        json=mapping_payload(name="上限超過", lon=139.701),
    )
    assert blocked.status_code == 429


def test_admin_session_uses_http_only_cookie(client: TestClient) -> None:
    failed = client.post("/api/admin/session", json={"key": "wrong"})
    assert failed.status_code == 401
    response = client.post("/api/admin/session", json={"key": "test-admin-key"})
    assert response.status_code == 200
    assert "HttpOnly" in response.headers["set-cookie"]
    assert client.get("/api/admin/mapping-submissions").status_code == 200
    logout = client.delete("/api/admin/session")
    assert logout.status_code == 204
    assert client.get("/api/admin/mapping-submissions").status_code == 401


def test_admin_can_filter_edit_mark_needs_verification_and_view_comparison(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/mapping-submissions",
        headers={"X-Client-Id": "client-admin-detail"},
        json=mapping_payload(category="construction"),
    ).json()
    detail = client.get(
        f"/api/admin/mapping-submissions/{created['id']}",
        headers=admin_headers(),
    )
    assert detail.status_code == 200
    assert detail.json()["official_nearby"]
    updated = client.patch(
        f"/api/admin/mapping-submissions/{created['id']}",
        headers=admin_headers(),
        json={
            "status": "needs_verification",
            "review_note": "位置と期間を追加確認する",
            "name": "工事情報（要確認）",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "needs_verification"
    assert updated.json()["name"] == "工事情報（要確認）"
    filtered = client.get(
        "/api/admin/mapping-submissions",
        headers=admin_headers(),
        params={"status": "needs_verification", "category": "construction"},
    )
    assert [item["id"] for item in filtered.json()] == [created["id"]]


def test_admin_audit_and_export(client: TestClient) -> None:
    created = client.post(
        "/api/mapping-submissions",
        headers={"X-Client-Id": "client-audit"},
        json=mapping_payload(),
    ).json()
    client.patch(
        f"/api/admin/mapping-submissions/{created['id']}",
        headers=admin_headers(),
        json={"status": "rejected", "review_note": "根拠不足のため却下"},
    )
    logs = client.get("/api/admin/audit-logs", headers=admin_headers())
    assert logs.status_code == 200
    actions = {item["action"] for item in logs.json()}
    assert {"submission_created", "submission_rejected"} <= actions
    json_export = client.get(
        "/api/admin/export", headers=admin_headers(), params={"format": "json"}
    )
    csv_export = client.get(
        "/api/admin/export", headers=admin_headers(), params={"format": "csv"}
    )
    assert json_export.status_code == 200
    assert "mapping-submissions.json" in json_export.headers["content-disposition"]
    assert csv_export.status_code == 200
    assert csv_export.text.startswith("\ufeff")


def test_submission_persists_across_application_lifespan(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/mapping-submissions",
        headers={"X-Client-Id": "client-persistence"},
        json=mapping_payload(),
    ).json()
    from app.main import app

    with TestClient(app) as restarted_client:
        listed = restarted_client.get(
            "/api/admin/mapping-submissions", headers=admin_headers()
        )
        assert any(item["id"] == created["id"] for item in listed.json())
