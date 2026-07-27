"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  fetchExits,
  fetchFloorMap,
  fetchGates,
  fetchHealth,
  fetchNetwork,
  fetchRoute,
} from "@/lib/api";
import type {
  FeatureCollection,
  HealthResponse,
  Place,
  RouteResponse,
} from "@/lib/types";

import styles from "./RoutePlanner.module.css";
import { RouteSummary } from "./RouteSummary";
import { SearchableSelect } from "./SearchableSelect";

const MapView = dynamic(
  () => import("./MapView").then((module) => module.MapView),
  {
    ssr: false,
    loading: () => (
      <div className={styles.mapLoading} role="status">
        地図を準備しています…
      </div>
    ),
  },
);

type LoadState = "loading" | "ready" | "routing" | "error" | "unreachable";

const DEFAULT_GATE_ID = "gate-1759781";
const DEFAULT_EXIT_ID = "exit-1760728";

const EMPTY_FEATURE_COLLECTION: FeatureCollection = {
  type: "FeatureCollection",
  features: [],
};

function preferredId(places: Place[], preferred: string): string {
  return places.some((place) => place.id === preferred)
    ? preferred
    : (places[0]?.id ?? "");
}

export function RoutePlanner() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [gates, setGates] = useState<Place[]>([]);
  const [exits, setExits] = useState<Place[]>([]);
  const [startGateId, setStartGateId] = useState("");
  const [destinationExitId, setDestinationExitId] = useState("");
  const [avoidStairs, setAvoidStairs] = useState(false);
  const [route, setRoute] = useState<RouteResponse | null>(null);
  const [selectedFloor, setSelectedFloor] = useState("B1");
  const [network, setNetwork] = useState<FeatureCollection>(
    EMPTY_FEATURE_COLLECTION,
  );
  const [floorMap, setFloorMap] = useState<FeatureCollection>(
    EMPTY_FEATURE_COLLECTION,
  );
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [message, setMessage] = useState("公開データを読み込んでいます…");

  useEffect(() => {
    let active = true;
    Promise.all([fetchHealth(), fetchGates(), fetchExits()])
      .then(([nextHealth, nextGates, nextExits]) => {
        if (!active) {
          return;
        }
        setHealth(nextHealth);
        setGates(nextGates);
        setExits(nextExits);
        setStartGateId(preferredId(nextGates, DEFAULT_GATE_ID));
        setDestinationExitId(preferredId(nextExits, DEFAULT_EXIT_ID));
        setLoadState("ready");
        setMessage("");
      })
      .catch((error: unknown) => {
        if (!active) {
          return;
        }
        setLoadState("error");
        setMessage(
          error instanceof Error
            ? error.message
            : "初期データを読み込めませんでした。",
        );
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    Promise.all([fetchNetwork(selectedFloor), fetchFloorMap(selectedFloor)])
      .then(([nextNetwork, nextFloorMap]) => {
        if (!active) {
          return;
        }
        setNetwork(nextNetwork);
        setFloorMap(nextFloorMap);
      })
      .catch((error: unknown) => {
        if (!active) {
          return;
        }
        setMessage(
          error instanceof Error
            ? `地図データ: ${error.message}`
            : "地図データを読み込めませんでした。",
        );
      });
    return () => {
      active = false;
    };
  }, [selectedFloor]);

  const routeFloors = useMemo(
    () => route?.floors ?? health?.floors ?? ["B1"],
    [health, route],
  );

  useEffect(() => {
    if (routeFloors.length > 0 && !routeFloors.includes(selectedFloor)) {
      setSelectedFloor(routeFloors[0]);
    }
  }, [routeFloors, selectedFloor]);

  const searchRoute = useCallback(async () => {
    if (!startGateId || !destinationExitId) {
      setLoadState("error");
      setMessage("出発改札と目的出口を選択してください。");
      return;
    }
    setLoadState("routing");
    setMessage("経路を計算しています…");
    setRoute(null);
    try {
      const nextRoute = await fetchRoute({
        start_gate_id: startGateId,
        destination_exit_id: destinationExitId,
        preferences: { avoid_stairs: avoidStairs },
      });
      setRoute(nextRoute);
      setSelectedFloor(nextRoute.floors[0] ?? "B1");
      setLoadState("ready");
      setMessage("");
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 422) {
        setLoadState("unreachable");
        setMessage(
          "この組合せは現在の歩行ネットワークでは到達できません。別の改札または出口を選択してください。",
        );
        return;
      }
      setLoadState("error");
      setMessage(
        error instanceof Error
          ? error.message
          : "経路検索中にエラーが発生しました。",
      );
    }
  }, [avoidStairs, destinationExitId, startGateId]);

  const selectedStart =
    route?.start_gate ?? gates.find((place) => place.id === startGateId) ?? null;
  const selectedDestination =
    route?.destination_exit ??
    exits.find((place) => place.id === destinationExitId) ??
    null;

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>TOKYO OPEN DATA ROUTE FINDER</p>
          <h1>新宿地下ナビ</h1>
          <p className={styles.lead}>
            改札から出口まで、階層ごとの地下通路を地図と文章で案内します。
          </p>
        </div>
        <div className={styles.dataStatus}>
          <span aria-hidden="true" className={styles.statusDot} />
          {health?.data_mode === "open-data"
            ? "東京都オープンデータ読込済み"
            : "データ状態を確認中"}
        </div>
      </header>

      {health?.data_mode === "fixture" ? (
        <div className={styles.fixtureBanner} role="alert">
          注意: 現在はテスト用サンプルデータを表示しています。実データではありません。
        </div>
      ) : null}

      <div className={styles.workspace}>
        <aside className={styles.searchPanel} aria-label="経路検索">
          <div className={styles.panelHeading}>
            <span className={styles.stepNumber}>01</span>
            <div>
              <h2>経路を選ぶ</h2>
              <p>名称・会社・方面で絞り込めます</p>
            </div>
          </div>

          <SearchableSelect
            id="start-gate"
            label="出発改札"
            places={gates}
            value={startGateId}
            onChange={setStartGateId}
            disabled={loadState === "loading" || loadState === "routing"}
          />
          <div className={styles.connector} aria-hidden="true">
            ↓
          </div>
          <SearchableSelect
            id="destination-exit"
            label="目的出口"
            places={exits}
            value={destinationExitId}
            onChange={setDestinationExitId}
            disabled={loadState === "loading" || loadState === "routing"}
          />

          <label className={styles.preference}>
            <input
              type="checkbox"
              checked={avoidStairs}
              onChange={(event) => setAvoidStairs(event.target.checked)}
            />
            <span>
              <strong>階段を避ける</strong>
              <small>代替経路がある場合のみ</small>
            </span>
          </label>

          <button
            className={styles.searchButton}
            type="button"
            onClick={searchRoute}
            disabled={loadState === "loading" || loadState === "routing"}
          >
            {loadState === "routing" ? "計算中…" : "経路を検索"}
          </button>

          <div className={styles.sourceNote}>
            <strong>データについて</strong>
            <p>
              東京都都市整備局「新宿駅周辺屋内地図オープンデータ」を使用。現地の案内表示を優先してください。
            </p>
            <a
              href="https://catalog.data.metro.tokyo.lg.jp/dataset/t000008d0000000037"
              target="_blank"
              rel="noreferrer"
            >
              出典と利用条件を確認 ↗
            </a>
          </div>
        </aside>

        <section className={styles.mapPanel} aria-label="階層別地図">
          <div className={styles.mapToolbar}>
            <div>
              <span className={styles.mapLabel}>表示階層</span>
              <div className={styles.floorTabs} role="group" aria-label="表示階層">
                {routeFloors.map((floor) => (
                  <button
                    key={floor}
                    type="button"
                    className={
                      floor === selectedFloor ? styles.activeFloor : undefined
                    }
                    aria-pressed={floor === selectedFloor}
                    onClick={() => setSelectedFloor(floor)}
                  >
                    {floor}
                  </button>
                ))}
              </div>
            </div>
            <p className={styles.mapHint}>ドラッグで移動・±で拡大縮小</p>
          </div>

          <div className={styles.mapFrame}>
            <MapView
              floor={selectedFloor}
              floorMap={floorMap}
              network={network}
              route={route}
              start={selectedStart}
              destination={selectedDestination}
            />
          </div>

          {message ? (
            <div
              className={`${styles.message} ${
                loadState === "unreachable" ? styles.unreachable : ""
              }`}
              role={loadState === "error" || loadState === "unreachable" ? "alert" : "status"}
            >
              <strong>
                {loadState === "unreachable"
                  ? "到達不能"
                  : loadState === "error"
                    ? "読込みエラー"
                    : "処理中"}
              </strong>
              <span>{message}</span>
            </div>
          ) : null}
        </section>

        <aside className={styles.routePanel} aria-label="経路案内">
          <div className={styles.panelHeading}>
            <span className={styles.stepNumber}>02</span>
            <div>
              <h2>経路案内</h2>
              <p>地図の階層は手動で切り替えられます</p>
            </div>
          </div>
          {route ? (
            <RouteSummary route={route} />
          ) : (
            <div className={styles.emptyRoute}>
              <span aria-hidden="true">↗</span>
              <h3>経路を検索してください</h3>
              <p>推定距離、経由階層、主要地点、案内文をここに表示します。</p>
            </div>
          )}
        </aside>
      </div>

      <footer className={styles.footer}>
        <span>位置情報は取得しません</span>
        <span>・</span>
        <span>現地の標識・係員の案内を優先してください</span>
      </footer>
    </main>
  );
}
