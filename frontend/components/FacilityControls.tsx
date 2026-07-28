"use client";

import { useMemo } from "react";

import { FACILITY_META } from "@/lib/facilities";
import type { Facility, FacilityCategory } from "@/lib/types";

import styles from "./RoutePlanner.module.css";

interface Props {
  facilities: Facility[];
  selected: Set<FacilityCategory>;
  query: string;
  onSelectedChange: (next: Set<FacilityCategory>) => void;
  onQueryChange: (value: string) => void;
}

export function FacilityControls({ facilities, selected, query, onSelectedChange, onQueryChange }: Props) {
  const counts = useMemo(() => {
    const result = new Map<FacilityCategory, number>();
    facilities.forEach((facility) => result.set(facility.category, (result.get(facility.category) ?? 0) + 1));
    return result;
  }, [facilities]);

  function toggle(category: FacilityCategory) {
    const next = new Set(selected);
    if (next.has(category)) next.delete(category);
    else next.add(category);
    onSelectedChange(next);
  }

  return (
    <details className={styles.facilityControls}>
      <summary>店舗・施設の表示</summary>
      <div>
        <label htmlFor="facility-search">名称検索</label>
        <input id="facility-search" type="search" value={query} placeholder="店舗・ATM・トイレなど" onChange={(event) => onQueryChange(event.target.value)} />
        <div className={styles.categoryGrid} role="group" aria-label="施設カテゴリ">
          {(Object.keys(FACILITY_META) as FacilityCategory[]).map((category) => {
            const count = counts.get(category) ?? 0;
            if (!count) return null;
            const meta = FACILITY_META[category];
            return (
              <button key={category} type="button" aria-pressed={selected.has(category)} className={selected.has(category) ? styles.categoryActive : undefined} onClick={() => toggle(category)}>
                <i style={{ background: meta.color }}>{meta.symbol}</i><span>{meta.label}</span><small>{count}</small>
              </button>
            );
          })}
        </div>
      </div>
    </details>
  );
}
