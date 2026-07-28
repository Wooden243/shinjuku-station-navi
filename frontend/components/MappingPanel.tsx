"use client";

import { useEffect, useState } from "react";

import { submitMapping } from "@/lib/api";
import {
  enqueueSubmission,
  listQueuedSubmissions,
  removeQueuedSubmission,
  updateQueuedSubmission,
} from "@/lib/offline-storage";
import type { MappingCategory, MappingSubmissionCreate } from "@/lib/types";

import styles from "./RoutePlanner.module.css";

const CATEGORIES: Array<[MappingCategory, string]> = [
  ["facility_add", "店舗・施設の追加"],
  ["name_correction", "名称の修正"],
  ["exit_note", "出口情報の補足"],
  ["landmark", "目印の追加"],
  ["closure", "閉店・一時閉鎖"],
  ["relocation", "移転"],
  ["passage_closure", "通路の閉鎖"],
  ["construction", "工事情報"],
  ["accessibility", "バリアフリー設備"],
  ["other", "その他"],
];

export async function syncPendingSubmissions(): Promise<{ sent: number; remaining: number }> {
  const queued = await listQueuedSubmissions();
  let sent = 0;
  for (const item of queued) {
    try {
      await submitMapping(item.payload);
      await removeQueuedSubmission(item.payload.client_submission_id);
      sent += 1;
    } catch (error) {
      await updateQueuedSubmission({
        ...item,
        attempts: item.attempts + 1,
        last_error: error instanceof Error ? error.message : "同期エラー",
      });
    }
  }
  return { sent, remaining: queued.length - sent };
}

interface Props {
  floor: string;
  picked: [number, number] | null;
  onStartPicking: () => void;
}

export function MappingPanel({ floor, picked, onStartPicking }: Props) {
  const [category, setCategory] = useState<MappingCategory>("facility_add");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [sourceMethod, setSourceMethod] = useState("");
  const [supplemental, setSupplemental] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const sync = () => void syncPendingSubmissions().then(({ sent }) => {
      if (sent) setMessage(`${sent}件の保存済み投稿を同期しました。`);
    });
    window.addEventListener("online", sync);
    if (navigator.onLine) sync();
    return () => window.removeEventListener("online", sync);
  }, []);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!picked) {
      setMessage("先に「地図で位置を指定」を押し、地図をタップしてください。");
      return;
    }
    const payload: MappingSubmissionCreate = {
      client_submission_id: crypto.randomUUID(),
      category,
      name: name.trim(),
      description: description.trim(),
      floor,
      lon: picked[0],
      lat: picked[1],
      source_method: sourceMethod.trim(),
      supplemental: supplemental.trim() || null,
      observed_at: new Date().toISOString(),
    };
    try {
      await submitMapping(payload);
      setMessage("審査待ちとして受け付けました。承認まで一般地図には表示されません。");
      setName("");
      setDescription("");
      setSupplemental("");
    } catch (error) {
      await enqueueSubmission(payload, error instanceof Error ? error.message : "通信エラー");
      setMessage("通信できないため端末内に保存しました。接続回復時に自動送信します。");
    }
  }

  return (
    <details className={styles.mappingPanel}>
      <summary>地図情報を投稿する</summary>
      <form onSubmit={submit}>
        <p className={styles.privacyNote}>氏名・メール・GPS履歴は収集しません。投稿は審査後に公開されます。</p>
        <button type="button" className={styles.secondaryButton} onClick={onStartPicking}>地図で位置を指定</button>
        <output>{picked ? `${floor} / ${picked[1].toFixed(6)}, ${picked[0].toFixed(6)}` : "位置未指定"}</output>
        <label>カテゴリ<select value={category} onChange={(e) => setCategory(e.target.value as MappingCategory)}>{CATEGORIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label>名称<input required maxLength={120} value={name} onChange={(e) => setName(e.target.value)} /></label>
        <label>内容<textarea required maxLength={1000} value={description} onChange={(e) => setDescription(e.target.value)} /></label>
        <label>情報源または確認方法<input required maxLength={240} value={sourceMethod} onChange={(e) => setSourceMethod(e.target.value)} placeholder="例：2026年7月28日に現地掲示を確認" /></label>
        <label>補足（任意）<textarea maxLength={1000} value={supplemental} onChange={(e) => setSupplemental(e.target.value)} /></label>
        <button type="submit" className={styles.searchButton}>審査へ送る</button>
        {message ? <p role="status">{message}</p> : null}
      </form>
    </details>
  );
}
