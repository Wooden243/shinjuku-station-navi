import type {
  MappingSubmissionCreate,
  OfflineBundle,
  OfflineDataStatus,
} from "@/lib/types";

const DATABASE_NAME = "shinjuku-underground-navi";
const DATABASE_VERSION = 2;
const BUNDLE_STORE = "bundles";
const QUEUE_STORE = "submission-queue";
const ACTIVE_BUNDLE_KEY = "active";
const CLIENT_ID_KEY = "shinjuku-nav-client-id";

let memoryBundle: OfflineBundle | null = null;
const memoryQueue = new Map<string, QueuedSubmission>();

export interface QueuedSubmission {
  payload: MappingSubmissionCreate;
  queued_at: string;
  attempts: number;
  last_error: string | null;
}

function indexedDbAvailable(): boolean {
  return typeof window !== "undefined" && "indexedDB" in window;
}

function openDatabase(): Promise<IDBDatabase> {
  if (!indexedDbAvailable()) {
    return Promise.reject(new Error("IndexedDBを利用できません"));
  }
  return new Promise((resolve, reject) => {
    const request = window.indexedDB.open(DATABASE_NAME, DATABASE_VERSION);
    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(BUNDLE_STORE)) {
        database.createObjectStore(BUNDLE_STORE);
      }
      if (!database.objectStoreNames.contains(QUEUE_STORE)) {
        database.createObjectStore(QUEUE_STORE, { keyPath: "payload.client_submission_id" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () =>
      reject(request.error ?? new Error("IndexedDBを開けません"));
    request.onblocked = () =>
      reject(new Error("別タブが古いオフラインDBを使用しています"));
  });
}

async function withStore<T>(
  storeName: string,
  mode: IDBTransactionMode,
  action: (store: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  const database = await openDatabase();
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(storeName, mode);
    const request = action(transaction.objectStore(storeName));
    request.onsuccess = () => resolve(request.result);
    request.onerror = () =>
      reject(request.error ?? new Error("IndexedDB操作に失敗しました"));
    transaction.oncomplete = () => database.close();
    transaction.onabort = () => {
      database.close();
      reject(transaction.error ?? new Error("IndexedDB操作が中断されました"));
    };
  });
}

export async function saveOfflineBundle(
  bundle: OfflineBundle,
): Promise<OfflineDataStatus> {
  memoryBundle = bundle;
  try {
    await withStore(BUNDLE_STORE, "readwrite", (store) =>
      store.put(bundle, ACTIVE_BUNDLE_KEY),
    );
    return statusFromBundle(bundle, "indexeddb", null);
  } catch (error) {
    return statusFromBundle(
      bundle,
      "memory",
      error instanceof Error
        ? `端末保存に失敗しました: ${error.message}`
        : "端末保存に失敗しました",
    );
  }
}

export async function loadOfflineBundle(): Promise<{
  bundle: OfflineBundle | null;
  storage: OfflineDataStatus["storage"];
  warning: string | null;
}> {
  try {
    const bundle = await withStore<OfflineBundle | undefined>(
      BUNDLE_STORE,
      "readonly",
      (store) => store.get(ACTIVE_BUNDLE_KEY),
    );
    if (bundle) {
      memoryBundle = bundle;
      return { bundle, storage: "indexeddb", warning: null };
    }
  } catch (error) {
    if (memoryBundle) {
      return {
        bundle: memoryBundle,
        storage: "memory",
        warning:
          error instanceof Error
            ? `IndexedDBを利用できないため一時メモリを使用中: ${error.message}`
            : "IndexedDBを利用できないため一時メモリを使用中",
      };
    }
    return {
      bundle: null,
      storage: "none",
      warning:
        error instanceof Error
          ? `保存済みデータを読めません: ${error.message}`
          : "保存済みデータを読めません",
    };
  }
  return {
    bundle: memoryBundle,
    storage: memoryBundle ? "memory" : "none",
    warning: null,
  };
}

export function statusFromBundle(
  bundle: OfflineBundle | null,
  storage: OfflineDataStatus["storage"],
  warning: string | null,
): OfflineDataStatus {
  return {
    available: bundle !== null,
    version: bundle?.version ?? null,
    generatedAt: bundle?.generated_at ?? null,
    sourceUpdatedAt: bundle?.source_updated_at ?? null,
    storage,
    warning,
  };
}

export async function enqueueSubmission(
  payload: MappingSubmissionCreate,
  errorMessage: string | null = null,
): Promise<void> {
  const queued: QueuedSubmission = {
    payload,
    queued_at: new Date().toISOString(),
    attempts: 0,
    last_error: errorMessage,
  };
  memoryQueue.set(payload.client_submission_id, queued);
  try {
    await withStore(QUEUE_STORE, "readwrite", (store) => store.put(queued));
  } catch {
    // メモリキューを残し、画面側で永続保存失敗を通知する。
  }
}

export async function listQueuedSubmissions(): Promise<QueuedSubmission[]> {
  try {
    const items = await withStore<QueuedSubmission[]>(
      QUEUE_STORE,
      "readonly",
      (store) => store.getAll(),
    );
    for (const item of items) {
      memoryQueue.set(item.payload.client_submission_id, item);
    }
    return items;
  } catch {
    return [...memoryQueue.values()];
  }
}

export async function updateQueuedSubmission(
  item: QueuedSubmission,
): Promise<void> {
  memoryQueue.set(item.payload.client_submission_id, item);
  try {
    await withStore(QUEUE_STORE, "readwrite", (store) => store.put(item));
  } catch {
    // メモリ側は更新済み。
  }
}

export async function removeQueuedSubmission(id: string): Promise<void> {
  memoryQueue.delete(id);
  try {
    await withStore(QUEUE_STORE, "readwrite", (store) => store.delete(id));
  } catch {
    // メモリ側は削除済み。
  }
}

export function getAnonymousClientId(): string {
  if (typeof window === "undefined") return "server-render";
  try {
    const existing = window.localStorage.getItem(CLIENT_ID_KEY);
    if (existing) return existing;
    const generated = window.crypto.randomUUID();
    window.localStorage.setItem(CLIENT_ID_KEY, generated);
    return generated;
  } catch {
    return `ephemeral-${window.crypto.randomUUID()}`;
  }
}
