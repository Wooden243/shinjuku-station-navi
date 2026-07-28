"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import {
  createAdminSession,
  deleteAdminSession,
  fetchAdminMappingDetail,
  fetchAdminMappings,
  fetchAuditLogs,
  reviewMapping,
  type AdminFilters,
} from "@/lib/api";
import { apiUrl } from "@/lib/api-url";
import type { AdminSubmissionDetail, AuditLog, MappingStatus, MappingSubmission } from "@/lib/types";

import styles from "./admin.module.css";

const STATUSES: Array<[MappingStatus | "", string]> = [
  ["", "すべて"], ["pending", "審査待ち"], ["approved", "承認済み"],
  ["rejected", "却下"], ["needs_verification", "要確認"], ["archived", "廃止"],
];

export default function AdminPage() {
  const [key, setKey] = useState("");
  const [authenticated, setAuthenticated] = useState(false);
  const [items, setItems] = useState<MappingSubmission[]>([]);
  const [detail, setDetail] = useState<AdminSubmissionDetail | null>(null);
  const [audits, setAudits] = useState<AuditLog[]>([]);
  const [filters, setFilters] = useState<AdminFilters>({ status: "", category: "", floor: "", sort: "newest" });
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    try {
      const [nextItems, nextAudits] = await Promise.all([fetchAdminMappings(filters), fetchAuditLogs()]);
      setItems(nextItems);
      setAudits(nextAudits);
      setAuthenticated(true);
      setMessage("");
    } catch (error) {
      setAuthenticated(false);
      setMessage(error instanceof Error ? error.message : "管理APIへ接続できません。");
    }
  }, [filters]);

  useEffect(() => { void load(); }, [load]);

  async function login(event: React.FormEvent) {
    event.preventDefault();
    try {
      await createAdminSession(key);
      setKey("");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "認証に失敗しました。");
    }
  }

  async function select(item: MappingSubmission) {
    const next = await fetchAdminMappingDetail(item.id);
    setDetail(next);
    setNote(next.submission.review_note);
  }

  async function review(status: MappingStatus) {
    if (!detail) return;
    try {
      const updated = await reviewMapping(detail.submission.id, { status, review_note: note });
      setDetail({ ...detail, submission: updated });
      await load();
      setMessage("審査結果と監査ログを保存しました。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "更新できませんでした。");
    }
  }

  return (
    <main className={styles.shell}>
      <header><div><p>TOKYO OPEN DATA / MODERATION</p><h1>管理者審査</h1></div><Link href="/">利用者画面へ戻る</Link></header>
      {!authenticated ? (
        <form className={styles.login} onSubmit={login}>
          <h2>開発用ログイン</h2>
          <p>キーはサーバーの環境変数にのみ設定します。本番ではOIDC対応プロキシを使用してください。</p>
          <label>開発用管理キー<input type="password" required value={key} onChange={(event) => setKey(event.target.value)} /></label>
          <button type="submit">ログイン</button>
          {message ? <p role="alert">{message}</p> : null}
        </form>
      ) : (
        <>
          <section className={styles.toolbar}>
            <label>状態<select value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value as MappingStatus | "" })}>{STATUSES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
            <label>カテゴリ<input value={filters.category} onChange={(e) => setFilters({ ...filters, category: e.target.value })} /></label>
            <label>階層<input value={filters.floor} onChange={(e) => setFilters({ ...filters, floor: e.target.value })} /></label>
            <label>並べ替え<select value={filters.sort} onChange={(e) => setFilters({ ...filters, sort: e.target.value as AdminFilters["sort"] })}><option value="newest">投稿日（新しい順）</option><option value="oldest">投稿日（古い順）</option><option value="supports">支持件数順</option></select></label>
            <a href={apiUrl("/api/admin/mapping-submissions/export?format=csv")}>CSV出力</a>
            <a href={apiUrl("/api/admin/mapping-submissions/export?format=json")}>JSON出力</a>
            <button type="button" onClick={async () => { await deleteAdminSession(); setAuthenticated(false); }}>ログアウト</button>
          </section>
          {message ? <p className={styles.message} role="status">{message}</p> : null}
          <div className={styles.workspace}>
            <section className={styles.list}>
              <h2>投稿一覧 <small>{items.length}件</small></h2>
              {items.map((item) => <button type="button" key={item.id} onClick={() => void select(item)} aria-pressed={detail?.submission.id === item.id}><strong>{item.name}</strong><span>{item.status}・{item.category}・{item.floor}</span><small>支持 {item.support_count} / {new Date(item.created_at).toLocaleString("ja-JP")}</small></button>)}
            </section>
            <section className={styles.detail}>
              {!detail ? <p>投稿を選択してください。</p> : <>
                <h2>{detail.submission.name}</h2>
                <dl>
                  <div><dt>状態</dt><dd>{detail.submission.status}</dd></div>
                  <div><dt>内容</dt><dd>{detail.submission.description}</dd></div>
                  <div><dt>確認方法</dt><dd>{detail.submission.source_method}</dd></div>
                  <div><dt>位置</dt><dd>{detail.submission.floor} / {detail.submission.lat.toFixed(6)}, {detail.submission.lon.toFixed(6)}</dd></div>
                </dl>
                <div className={styles.position} aria-label="投稿位置"><span style={{ left: "50%", top: "50%" }}>●</span><p>投稿座標（地図データとの比較は下記一覧で確認）</p></div>
                <h3>類似投稿</h3>
                {detail.similar.length ? <ul>{detail.similar.map((item) => <li key={item.id}>#{item.id} {item.name} / {item.status} / 支持{item.support_count}</li>)}</ul> : <p>類似投稿なし</p>}
                <h3>近隣の公式データ</h3>
                {detail.official_nearby.length ? <ul>{detail.official_nearby.map((item) => <li key={`${item.kind}-${item.id}`}>{item.name}（{item.floor}・約{item.distance_meters.toFixed(1)}m）</li>)}</ul> : <p>近隣データなし</p>}
                <label>審査理由・メモ<textarea value={note} maxLength={1000} onChange={(e) => setNote(e.target.value)} /></label>
                <div className={styles.actions}>
                  <button type="button" onClick={() => void review("approved")}>承認</button>
                  <button type="button" onClick={() => void review("needs_verification")}>要確認</button>
                  <button type="button" onClick={() => void review("rejected")}>却下</button>
                  <button type="button" onClick={() => void review("archived")}>廃止</button>
                </div>
              </>}
            </section>
            <section className={styles.audit}><h2>監査ログ</h2><ol>{audits.slice(0, 100).map((log) => <li key={log.id}><strong>{log.action}</strong><span>{log.actor}・{new Date(log.created_at).toLocaleString("ja-JP")}</span></li>)}</ol></section>
          </div>
        </>
      )}
    </main>
  );
}
