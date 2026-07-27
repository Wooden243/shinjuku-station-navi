import type { RouteResponse } from "@/lib/types";

import styles from "./RoutePlanner.module.css";

interface RouteSummaryProps {
  route: RouteResponse;
}

export function RouteSummary({ route }: RouteSummaryProps) {
  const routeLandmarks = route.landmarks.slice(0, 8);
  return (
    <div className={styles.summary}>
      <div className={styles.routeEndpoints}>
        <div>
          <span>出発</span>
          <strong>{route.start_gate.name}</strong>
          <small>
            {route.start_gate.operator}・{route.start_gate.floor}
          </small>
        </div>
        <span className={styles.endpointArrow} aria-hidden="true">
          ↓
        </span>
        <div>
          <span>到着</span>
          <strong>{route.destination_exit.name}</strong>
          <small>
            {route.destination_exit.direction}・{route.destination_exit.floor}
          </small>
        </div>
      </div>

      <dl className={styles.metrics}>
        <div>
          <dt>推定距離</dt>
          <dd>
            {Math.round(route.distance_meters)}
            <small>m</small>
          </dd>
        </div>
        <div>
          <dt>徒歩目安</dt>
          <dd>
            {route.estimated_walking_minutes.toFixed(1)}
            <small>分</small>
          </dd>
        </div>
        <div>
          <dt>階層移動</dt>
          <dd>
            {route.floor_transitions.length}
            <small>回</small>
          </dd>
        </div>
      </dl>

      <div className={styles.floorSummary}>
        <strong>経由階層</strong>
        <span>{route.floors.join(" → ")}</span>
      </div>

      <section className={styles.instructionsSection}>
        <h3>経路案内</h3>
        <ol className={styles.instructions}>
          {route.instructions.map((instruction) => (
            <li key={instruction.order}>
              <span>{instruction.floor}</span>
              <p>{instruction.text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className={styles.landmarks}>
        <h3>経路上の主要地点</h3>
        {routeLandmarks.length === 0 ? (
          <p className={styles.mutedText}>登録済みの主要地点はありません。</p>
        ) : (
          <ul>
            {routeLandmarks.map((landmark) => (
              <li key={landmark.id}>
                <div>
                  <strong>{landmark.name}</strong>
                  <span>{landmark.floor}</span>
                </div>
                <p>{landmark.description}</p>
                {landmark.photo_url === null ? (
                  <small>写真なし</small>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className={styles.warningBox} aria-labelledby="warnings-title">
        <h3 id="warnings-title">データ上の注意事項</h3>
        <ul>
          {route.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
