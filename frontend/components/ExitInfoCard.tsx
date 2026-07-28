import type { Place, ProvenanceKind } from "@/lib/types";

import styles from "./RoutePlanner.module.css";

const LABELS: Record<ProvenanceKind, string> = {
  "open-data": "オープンデータ",
  "derived-open-data": "公開データから算出",
  "operator-verified": "運営者確認",
  "admin-correction": "管理者補正",
  "user-submission": "利用者投稿",
  unverified: "未確認",
  "no-data": "情報なし",
};

function provenance(exit: Place, field: string, fallback: ProvenanceKind = "no-data") {
  return LABELS[exit.provenance[field] ?? fallback];
}

function display(value: string | null | undefined, fallback = "情報なし") {
  return value?.trim() || fallback;
}

interface Props {
  exit: Place;
  compact?: boolean;
}

export function ExitInfoCard({ exit, compact = false }: Props) {
  return (
    <details className={styles.exitCard} open={!compact}>
      <summary>
        <span>
          <small>選択中の出口</small>
          <strong>{exit.official_name ?? exit.name}</strong>
        </span>
        <span aria-hidden="true">詳細</span>
      </summary>
      <div className={styles.exitCardBody}>
        <dl className={styles.exitDetails}>
          <div>
            <dt>出口番号・正式名称</dt>
            <dd>{display(exit.exit_number)}・{display(exit.official_name ?? exit.name)}<small>{provenance(exit, "official_name")}</small></dd>
          </div>
          <div>
            <dt>階層</dt>
            <dd>{exit.floor}<small>{provenance(exit, "floor")}</small></dd>
          </div>
          <div>
            <dt>道路・方面</dt>
            <dd>{display(exit.road_or_direction)}<small>{provenance(exit, "road_or_direction")}</small></dd>
          </div>
          <div>
            <dt>周辺の主要施設</dt>
            <dd>
              {exit.nearby_landmarks.length
                ? exit.nearby_landmarks.map((item) => `${item.name}（直線約${Math.round(item.distance_meters)}m）`).join("、")
                : "情報なし"}
              <small>{provenance(exit, "nearby_landmarks")}</small>
            </dd>
          </div>
          <div>
            <dt>設備</dt>
            <dd>{exit.equipment.length ? exit.equipment.join("、") : "情報なし"}<small>{provenance(exit, "equipment")}</small></dd>
          </div>
          <div>
            <dt>バリアフリー</dt>
            <dd>{display(exit.accessibility, "未確認")}<small>{provenance(exit, "accessibility", "unverified")}</small></dd>
          </div>
          <div>
            <dt>利用可能時間</dt>
            <dd>{display(exit.available_hours)}<small>{provenance(exit, "available_hours")}</small></dd>
          </div>
          <div>
            <dt>閉鎖・工事等</dt>
            <dd>{exit.closure_notes.length ? exit.closure_notes.join("、") : "情報なし"}<small>{provenance(exit, "closure_notes")}</small></dd>
          </div>
          <div>
            <dt>現地確認</dt>
            <dd>{exit.verification_status === "verified-on-site" ? "確認済み" : "運営者による現地確認は未実施"}<small>{provenance(exit, "verification_status", "unverified")}</small></dd>
          </div>
        </dl>
        <p className={styles.exitSource}>
          更新日: {exit.data_updated_at ? new Date(exit.data_updated_at).toLocaleDateString("ja-JP") : "情報なし"}
          <br />
          出典: {exit.source ? <a href={exit.source.url} target="_blank" rel="noreferrer">{exit.source.provider}「{exit.source.title}」</a> : "情報なし"}
        </p>
      </div>
    </details>
  );
}
