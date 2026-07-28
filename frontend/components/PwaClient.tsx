"use client";

import { useEffect, useState } from "react";

import styles from "./PwaClient.module.css";

interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

export function PwaClient() {
  const [install, setInstall] = useState<BeforeInstallPromptEvent | null>(null);
  const [update, setUpdate] = useState<ServiceWorkerRegistration | null>(null);

  useEffect(() => {
    const installHandler = (event: Event) => {
      event.preventDefault();
      setInstall(event as BeforeInstallPromptEvent);
    };
    window.addEventListener("beforeinstallprompt", installHandler);
    if ("serviceWorker" in navigator && process.env.NODE_ENV === "production") {
      navigator.serviceWorker.register("/sw.js").then((registration) => {
        if (registration.waiting) setUpdate(registration);
        registration.addEventListener("updatefound", () => {
          registration.installing?.addEventListener("statechange", () => {
            if (registration.waiting && navigator.serviceWorker.controller) setUpdate(registration);
          });
        });
      }).catch(() => undefined);
    }
    return () => window.removeEventListener("beforeinstallprompt", installHandler);
  }, []);

  if (!install && !update) return null;
  return (
    <div className={styles.notice} role="status">
      {install ? <button type="button" onClick={async () => { await install.prompt(); await install.userChoice; setInstall(null); }}>アプリをインストール</button> : null}
      {update ? <button type="button" onClick={() => { update.waiting?.postMessage({ type: "SKIP_WAITING" }); window.location.reload(); }}>更新版を適用</button> : null}
      <span>初回のオフライン保存にはオンライン接続が必要です。</span>
    </div>
  );
}
