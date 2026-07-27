"use client";

import { useMemo, useState } from "react";

import type { Place } from "@/lib/types";

import styles from "./RoutePlanner.module.css";

interface SearchableSelectProps {
  id: string;
  label: string;
  places: Place[];
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}

export function placeOptionLabel(place: Place): string {
  const sourceId =
    place.source_geometry_id === null
      ? "公開IDなし"
      : `公開ID ${place.source_geometry_id}`;
  return [
    place.name,
    place.operator,
    place.direction,
    place.floor,
    sourceId,
  ].join("｜");
}

export function SearchableSelect({
  id,
  label,
  places,
  value,
  onChange,
  disabled = false,
}: SearchableSelectProps) {
  const [query, setQuery] = useState("");
  const normalizedQuery = query.trim().toLocaleLowerCase("ja");
  const filtered = useMemo(
    () =>
      normalizedQuery
        ? places.filter((place) =>
            placeOptionLabel(place)
              .toLocaleLowerCase("ja")
              .includes(normalizedQuery),
          )
        : places,
    [normalizedQuery, places],
  );

  const updateQuery = (nextQuery: string) => {
    setQuery(nextQuery);
    const nextNormalizedQuery = nextQuery.trim().toLocaleLowerCase("ja");
    const nextPlaces = nextNormalizedQuery
      ? places.filter((place) =>
          placeOptionLabel(place)
            .toLocaleLowerCase("ja")
            .includes(nextNormalizedQuery),
        )
      : places;
    if (!nextPlaces.some((place) => place.id === value)) {
      onChange(nextPlaces[0]?.id ?? "");
    }
  };

  const selectedValue = filtered.some((place) => place.id === value)
    ? value
    : "";

  return (
    <div className={styles.fieldGroup}>
      <label htmlFor={`${id}-search`}>{label}</label>
      <input
        id={`${id}-search`}
        type="search"
        value={query}
        placeholder={`${label}を検索`}
        onChange={(event) => updateQuery(event.target.value)}
        disabled={disabled}
      />
      <select
        id={id}
        aria-label={`${label}の候補`}
        value={selectedValue}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
      >
        {filtered.length === 0 ? (
          <option value="">一致する地点がありません</option>
        ) : (
          filtered.map((place) => (
            <option key={place.id} value={place.id}>
              {placeOptionLabel(place)}
            </option>
          ))
        )}
      </select>
      <span className={styles.fieldHint} aria-live="polite">
        {filtered.length}件
      </span>
    </div>
  );
}
