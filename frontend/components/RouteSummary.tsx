import type { RouteResponse } from "@/lib/types";

import styles from "./RoutePlanner.module.css";

export function RouteSummary({ route }: { route: RouteResponse }) {
  return (
    <div className={styles.summary}>
      {route.instructions[1] ? <div className={styles.nextAction}><small>次の行動</small><strong>{route.instructions[1].text}</strong></div> : null}
      <div className={styles.routeEndpoints}>
        <div><span>出発</span><strong>{route.start_gate.name}</strong><small>{route.start_gate.operator}・{route.start_gate.floor}</small></div>
        <span className={styles.endpointArrow} aria-hidden="true">↓</span>
        <div><span>到着</span><strong>{route.destination_exit.name}</strong><small>{route.destination_exit.direction}・{route.destination_exit.floor}</small></div>
      </div>
      <dl className={styles.metrics}>
        <div><dt>推定距離</dt><dd>{Math.round(route.distance_meters)}<small>m</small></dd></div>
        <div><dt>徒歩目安</dt><dd>{route.estimated_walking_minutes.toFixed(1)}<small>分</small></dd></div>
        <div><dt>階層移動</dt><dd>{route.floor_transitions.length}<small>回</small></dd></div>
      </dl>
      <div className={styles.floorSummary}><strong>経由階層</strong><span>{route.floors.join(" → ")}</span></div>
      <section className={styles.instructionsSection}>
        <h3>経路案内</h3>
        <ol className={styles.instructions}>
          {route.instructions.map((item) => <li key={item.order}><span>{item.floor}</span><p>{item.text}</p></li>)}
        </ol>
      </section>
      <section className={styles.warningBox}>
        <h3>安全上の注意</h3>
        <ul>{route.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
      </section>
    </div>
  );
}
