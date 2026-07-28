"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  fetchBootstrapData,
  fetchMapData,
  fetchPublicMappings,
  fetchRoute,
} from "@/lib/api";
import { DEFAULT_FACILITY_CATEGORIES } from "@/lib/facilities";
import { refreshOfflineData } from "@/lib/offline-routing";
import type {
  FacilityCategory,
  FeatureCollection,
  HealthResponse,
  MappingSubmission,
  OfflineBundle,
  OfflineDataStatus,
  Place,
  RouteResponse,
} from "@/lib/types";

import { ExitInfoCard } from "./ExitInfoCard";
import { FacilityControls } from "./FacilityControls";
import { MappingPanel } from "./MappingPanel";
import { RouteSummary } from "./RouteSummary";
import { SearchableSelect } from "./SearchableSelect";
import styles from "./RoutePlanner.module.css";

const MapView = dynamic(() => import("./MapView").then((module) => module.MapView), {
  ssr: false,
  loading: () => <div className={styles.mapLoading} role="status">地図を準備しています…</div>,
});

const EMPTY: FeatureCollection = { type: "FeatureCollection", features: [] };
type LoadState = "loading" | "ready" | "routing" | "error" | "unreachable";

function firstId(places: Place[], preferred: string) {
  return places.find((place) => place.id === preferred)?.id ?? places[0]?.id ?? "";
}

export function RoutePlanner() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [gates, setGates] = useState<Place[]>([]);
  const [exits, setExits] = useState<Place[]>([]);
  const [facilities, setFacilities] = useState<Awaited<ReturnType<typeof fetchBootstrapData>>["facilities"]>([]);
  const [mappings, setMappings] = useState<MappingSubmission[]>([]);
  const [bundle, setBundle] = useState<OfflineBundle | null>(null);
  const [offlineStatus, setOfflineStatus] = useState<OfflineDataStatus | null>(null);
  const [startGateId, setStartGateId] = useState("");
  const [destinationExitId, setDestinationExitId] = useState("");
  const [avoidStairs, setAvoidStairs] = useState(false);
  const [route, setRoute] = useState<RouteResponse | null>(null);
  const [selectedFloor, setSelectedFloor] = useState("B1");
  const [network, setNetwork] = useState<FeatureCollection>(EMPTY);
  const [floorMap, setFloorMap] = useState<FeatureCollection>(EMPTY);
  const [selectedCategories, setSelectedCategories] = useState<Set<FacilityCategory>>(() => new Set(DEFAULT_FACILITY_CATEGORIES));
  const [facilityQuery, setFacilityQuery] = useState("");
  const [selectedFacilityId, setSelectedFacilityId] = useState<string | null>(null);
  const [picked, setPicked] = useState<[number, number] | null>(null);
  const [picking, setPicking] = useState(false);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [message, setMessage] = useState("公開データを読み込んでいます…");
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    let active = true;
    fetchBootstrapData()
      .then((data) => {
        if (!active) return;
        setHealth(data.health);
        setGates(data.gates);
        setExits(data.exits);
        setFacilities(data.facilities);
        setBundle(data.bundle);
        setOffline(data.offline);
        setStartGateId(firstId(data.gates, "gate-1759781"));
        setDestinationExitId(firstId(data.exits, "exit-1760728"));
        setSelectedFloor(data.exits[0]?.floor ?? data.health.floors[0] ?? "B1");
        setLoadState("ready");
        setMessage("");
      })
      .catch((error: unknown) => {
        if (!active) return;
        setLoadState("error");
        setMessage(error instanceof Error ? error.message : "初回データを読み込めませんでした。");
      });
    void refreshOfflineData().then((status) => active && setOfflineStatus(status));
    void fetchPublicMappings().then((items) => active && setMappings(items)).catch(() => undefined);
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    fetchMapData(selectedFloor, bundle)
      .then((data) => {
        if (!active) return;
        setNetwork(data.network);
        setFloorMap(data.floorMap);
        setBundle(data.bundle);
        if (data.offline) setOffline(true);
      })
      .catch((error: unknown) => active && setMessage(error instanceof Error ? error.message : "地図を読み込めませんでした。"));
    return () => { active = false; };
  }, [selectedFloor, bundle]);

  const destination = exits.find((place) => place.id === destinationExitId) ?? null;
  const start = gates.find((place) => place.id === startGateId) ?? null;
  const routeFloorSet = useMemo(() => new Set(route?.floors ?? []), [route]);
  const visibleFacilities = useMemo(() => {
    const query = facilityQuery.trim().toLocaleLowerCase("ja");
    return facilities.filter((facility) =>
      facility.floor === selectedFloor &&
      selectedCategories.has(facility.category) &&
      (!query || `${facility.name} ${facility.description ?? ""}`.toLocaleLowerCase("ja").includes(query)),
    );
  }, [facilities, selectedFloor, selectedCategories, facilityQuery]);
  const selectedFacility = facilities.find((facility) => facility.id === selectedFacilityId) ?? null;

  const searchRoute = useCallback(async () => {
    if (!startGateId || !destinationExitId) {
      setLoadState("error");
      setMessage("出発改札と目的出口を選択してください。");
      return;
    }
    setLoadState("routing");
    setMessage("経路を計算しています…");
    try {
      const next = await fetchRoute({
        start_gate_id: startGateId,
        destination_exit_id: destinationExitId,
        preferences: { avoid_stairs: avoidStairs },
      });
      setRoute(next);
      setSelectedFloor(next.floors[0] ?? "B1");
      setOffline(next.route_id.startsWith("offline-"));
      setLoadState("ready");
      setMessage("");
    } catch (error) {
      const unreachable = error instanceof ApiError && error.status === 422;
      setLoadState(unreachable ? "unreachable" : "error");
      setMessage(unreachable
        ? "現在の歩行ネットワークでは到達できません。別の改札・出口を選択してください。架空の経路は表示しません。"
        : error instanceof Error ? error.message : "経路探索に失敗しました。");
    }
  }, [avoidStairs, destinationExitId, startGateId]);

  function selectExit(id: string) {
    setDestinationExitId(id);
    const selected = exits.find((item) => item.id === id);
    if (selected) setSelectedFloor(selected.floor);
  }

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>TOKYO OPEN DATA ROUTE FINDER</p>
          <h1>新宿地下ナビ</h1>
          <p className={styles.lead}>改札から出口まで、階層別の地図と文章で案内します。</p>
        </div>
        <nav className={styles.headerLinks}><Link href="/admin">管理画面</Link></nav>
      </header>

      <div className={`${styles.dataBanner} ${offline ? styles.offlineBanner : ""}`} role="status">
        <strong>{offline ? "オフラインデータを使用中" : "東京都オープンデータを使用中"}</strong>
        <span>更新: {offlineStatus?.sourceUpdatedAt ? new Date(offlineStatus.sourceUpdatedAt).toLocaleDateString("ja-JP") : health?.source.source_updated_at ? new Date(health.source.source_updated_at).toLocaleDateString("ja-JP") : "未確認"}</span>
        {offlineStatus?.warning ? <span>{offlineStatus.warning}</span> : null}
      </div>

      <div className={styles.workspace}>
        <aside className={styles.searchPanel} aria-label="経路検索">
          <div className={styles.panelHeading}><span className={styles.stepNumber}>01</span><div><h2>経路を選ぶ</h2><p>名称・方面・周辺施設でも検索できます</p></div></div>
          <SearchableSelect id="start-gate" label="出発改札" places={gates} value={startGateId} onChange={setStartGateId} disabled={loadState === "loading" || loadState === "routing"} />
          <div className={styles.connector} aria-hidden="true">↓</div>
          <SearchableSelect id="destination-exit" label="目的出口" places={exits} value={destinationExitId} onChange={selectExit} disabled={loadState === "loading" || loadState === "routing"} />
          <label className={styles.preference}><input type="checkbox" checked={avoidStairs} onChange={(event) => setAvoidStairs(event.target.checked)} /><span><strong>階段を避ける</strong><small>代替経路が存在する場合のみ</small></span></label>
          <button className={styles.searchButton} type="button" onClick={searchRoute} disabled={loadState === "loading" || loadState === "routing"}>{loadState === "routing" ? "計算中…" : "経路を検索"}</button>
          {destination ? <ExitInfoCard exit={destination} /> : null}
          <FacilityControls facilities={facilities} selected={selectedCategories} query={facilityQuery} onSelectedChange={setSelectedCategories} onQueryChange={setFacilityQuery} />
          <MappingPanel floor={selectedFloor} picked={picked} onStartPicking={() => { setPicking(true); setMessage("投稿する位置を地図上でタップしてください。"); }} />
          <div className={styles.sourceNote}><strong>出典</strong><p>東京都都市整備局「新宿駅周辺の施設情報等」を加工。CC BY。背景は転載画像を使わない簡略図です。</p><a href="https://catalog.data.metro.tokyo.lg.jp/dataset/t000008d0000000037" target="_blank" rel="noreferrer">データセットと利用条件</a></div>
        </aside>

        <section className={styles.mapPanel} aria-label="階層別地図">
          <div className={styles.mapToolbar}>
            <div><span className={styles.mapLabel}>表示階層</span><div className={styles.floorTabs} role="group" aria-label="表示階層">
              {(health?.floors ?? ["B1"]).map((floor) => <button key={floor} type="button" className={`${floor === selectedFloor ? styles.activeFloor : ""} ${routeFloorSet.has(floor) ? styles.routeFloor : ""}`} aria-pressed={floor === selectedFloor} onClick={() => setSelectedFloor(floor)}>{floor}</button>)}
            </div></div>
            <p className={styles.mapHint}>回転・拡大縮小・経路全体表示に対応</p>
          </div>
          {route?.instructions[1] ? <div className={styles.actionBanner}>{route.instructions[1].text}</div> : null}
          <div className={styles.mapFrame}>
            <MapView floor={selectedFloor} floorMap={floorMap} network={network} route={route} start={route?.start_gate ?? start} destination={route?.destination_exit ?? destination} gates={gates} exits={exits} facilities={visibleFacilities} mappings={mappings} onExitSelect={selectExit} onFacilitySelect={setSelectedFacilityId} onMapPick={(lon, lat) => { if (picking) { setPicked([lon, lat]); setPicking(false); setMessage("投稿位置を指定しました。"); } }} onReturnToStart={() => start && setSelectedFloor(start.floor)} />
          </div>
          {destination ? <div className={styles.mobileExitCard}><ExitInfoCard exit={destination} compact /></div> : null}
          {selectedFacility ? <div className={styles.facilityCard}><button type="button" onClick={() => setSelectedFacilityId(null)} aria-label="閉じる">×</button><strong>{selectedFacility.name}</strong><span>{selectedFacility.floor}・{selectedFacility.public_category ?? "施設"}</span><p>{selectedFacility.description ?? "説明なし"}</p><small>出典: {selectedFacility.source.provider} / 現地未確認</small></div> : null}
          {message ? <div className={`${styles.message} ${loadState === "unreachable" ? styles.unreachable : ""}`} role={loadState === "error" || loadState === "unreachable" ? "alert" : "status"}><strong>{loadState === "unreachable" ? "経路なし" : loadState === "error" ? "エラー" : "お知らせ"}</strong><span>{message}</span></div> : null}
        </section>

        <aside className={styles.routePanel} aria-label="経路案内">
          <div className={styles.panelHeading}><span className={styles.stepNumber}>02</span><div><h2>経路案内</h2><p>矢印の向きは出発から目的地の順です</p></div></div>
          {route ? <RouteSummary route={route} /> : <div className={styles.emptyRoute}><span aria-hidden="true">→</span><h3>経路を検索してください</h3><p>距離、階層移動、次の行動をここに表示します。</p></div>}
        </aside>
      </div>
      <footer className={styles.footer}><span>GPS・氏名・メールは取得しません</span><span>現地の案内表示と係員の指示を優先してください</span></footer>
    </main>
  );
}
