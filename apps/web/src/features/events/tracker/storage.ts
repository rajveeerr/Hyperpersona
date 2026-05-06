/**
 * IndexedDB layer for the event tracker.
 *
 * Why IndexedDB over `localStorage`:
 *   - async (no main-thread blocking on writes during a hot user flow),
 *   - large quota (so a stalled queue doesn't compete with cart/wishlist),
 *   - structured cloning (objects survive without manual JSON wrapping),
 *   - durable per-record writes (a tab kill between enqueue and flush still
 *     leaves events recoverable on the next session).
 *
 * Hand-rolled minimal Promise wrapper instead of pulling in `idb` — the API
 * surface here is small enough that adding a dependency is not justified.
 */

import { TRACKER_SCHEMA_VERSION, type StoredEvent } from "@/features/events/tracker/types";

const DB_NAME = "hyperpersona-events";
const DB_VERSION = 1;
const STORE = "pending";
const IDX_EMITTED_AT = "by_client_emitted_at";
const IDX_NEXT_ATTEMPT_AT = "by_next_attempt_at";

let dbPromise: Promise<IDBDatabase> | null = null;

function isIndexedDbAvailable(): boolean {
  return typeof indexedDB !== "undefined";
}

/**
 * Open and cache the database connection. The first call defines the schema.
 * Subsequent calls return the same `Promise<IDBDatabase>`.
 */
function openDb(): Promise<IDBDatabase> {
  if (!isIndexedDbAvailable()) {
    return Promise.reject(new Error("IndexedDB unavailable"));
  }
  if (dbPromise) return dbPromise;
  dbPromise = new Promise<IDBDatabase>((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        const store = db.createObjectStore(STORE, { keyPath: "client_event_id" });
        // FIFO drain order — read smallest emitted_at first.
        store.createIndex(IDX_EMITTED_AT, "client_emitted_at");
        // Backoff scheduler — events whose `next_attempt_at <= now` are eligible.
        store.createIndex(IDX_NEXT_ATTEMPT_AT, "next_attempt_at");
      }
    };
    req.onsuccess = () => {
      const db = req.result;
      // Recreate the cached promise on close so the next op re-opens cleanly.
      db.onclose = () => {
        dbPromise = null;
      };
      db.onversionchange = () => {
        // Another tab is upgrading — release this connection.
        db.close();
        dbPromise = null;
      };
      resolve(db);
    };
    req.onerror = () => reject(req.error ?? new Error("indexeddb open failed"));
    req.onblocked = () => reject(new Error("indexeddb open blocked"));
  });
  return dbPromise;
}

function tx(db: IDBDatabase, mode: IDBTransactionMode): IDBObjectStore {
  return db.transaction(STORE, mode).objectStore(STORE);
}

function promisifyRequest<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error("indexeddb request failed"));
  });
}

function promisifyTx(transaction: IDBTransaction): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    transaction.oncomplete = () => resolve();
    transaction.onabort = () => reject(transaction.error ?? new Error("indexeddb transaction aborted"));
    transaction.onerror = () => reject(transaction.error ?? new Error("indexeddb transaction failed"));
  });
}

/**
 * Persist a single event. Overwrite-on-collision is intentional — retries of
 * the same `client_event_id` (e.g. mid-flight failure replay) must replace
 * the prior row in place, not duplicate it.
 */
export async function enqueueEvent(event: StoredEvent): Promise<void> {
  const db = await openDb();
  const transaction = db.transaction(STORE, "readwrite");
  transaction.objectStore(STORE).put(event);
  await promisifyTx(transaction);
}

/** Return the oldest `limit` events whose `next_attempt_at <= now`. FIFO order. */
export async function loadDueEvents(limit: number, now = Date.now()): Promise<StoredEvent[]> {
  const db = await openDb();
  const store = tx(db, "readonly");
  const index = store.index(IDX_NEXT_ATTEMPT_AT);
  const range = IDBKeyRange.upperBound(now);
  return new Promise<StoredEvent[]>((resolve, reject) => {
    const out: StoredEvent[] = [];
    const cursorReq = index.openCursor(range, "next");
    cursorReq.onsuccess = () => {
      const cursor = cursorReq.result;
      if (!cursor || out.length >= limit) {
        // Sort by emitted_at to preserve FIFO when several events share the
        // same `next_attempt_at` (initial enqueue defaults to 0 / now).
        out.sort((a, b) => a.client_emitted_at - b.client_emitted_at);
        resolve(out);
        return;
      }
      out.push(cursor.value as StoredEvent);
      cursor.continue();
    };
    cursorReq.onerror = () => reject(cursorReq.error ?? new Error("indexeddb cursor failed"));
  });
}

export async function deleteEventsByIds(ids: string[]): Promise<void> {
  if (!ids.length) return;
  const db = await openDb();
  const transaction = db.transaction(STORE, "readwrite");
  const store = transaction.objectStore(STORE);
  for (const id of ids) store.delete(id);
  await promisifyTx(transaction);
}

/**
 * Reset retry metadata on every pending row — `next_attempt_at = 0`,
 * `attempt_count = 0`. Called from boot drain so events stuck on a stale
 * backoff timestamp from a prior session (e.g. a 5xx storm before refresh)
 * become immediately retriable. Returns the number of rows touched.
 */
export async function resetRetryMetadata(): Promise<number> {
  const db = await openDb();
  const transaction = db.transaction(STORE, "readwrite");
  const store = transaction.objectStore(STORE);
  let touched = 0;
  await new Promise<void>((resolve, reject) => {
    const cursorReq = store.openCursor();
    cursorReq.onsuccess = () => {
      const cursor = cursorReq.result;
      if (!cursor) {
        resolve();
        return;
      }
      const row = cursor.value as StoredEvent;
      if (row.next_attempt_at !== 0 || row.attempt_count !== 0) {
        row.next_attempt_at = 0;
        row.attempt_count = 0;
        cursor.update(row);
        touched += 1;
      }
      cursor.continue();
    };
    cursorReq.onerror = () => reject(cursorReq.error ?? new Error("indexeddb reset cursor failed"));
  });
  await promisifyTx(transaction);
  return touched;
}

/**
 * Bump retry metadata for a list of events that failed at the transport level.
 * Caller decides the next attempt timestamp (exponential backoff lives in
 * `tracker.ts` so the schedule is observable from one place).
 */
export async function markRetry(ids: string[], nextAttemptAt: number): Promise<void> {
  if (!ids.length) return;
  const db = await openDb();
  const transaction = db.transaction(STORE, "readwrite");
  const store = transaction.objectStore(STORE);
  for (const id of ids) {
    const getReq = store.get(id);
    getReq.onsuccess = () => {
      const row = getReq.result as StoredEvent | undefined;
      if (!row) return;
      row.attempt_count += 1;
      row.next_attempt_at = nextAttemptAt;
      store.put(row);
    };
  }
  await promisifyTx(transaction);
}

/** Drop events older than `cutoff` and any rows on a stale schema. */
export async function purgeStale(cutoff: number): Promise<number> {
  const db = await openDb();
  const transaction = db.transaction(STORE, "readwrite");
  const store = transaction.objectStore(STORE);
  const index = store.index(IDX_EMITTED_AT);
  let deleted = 0;
  await new Promise<void>((resolve, reject) => {
    const cursorReq = index.openCursor();
    cursorReq.onsuccess = () => {
      const cursor = cursorReq.result;
      if (!cursor) {
        resolve();
        return;
      }
      const row = cursor.value as StoredEvent;
      if (row.client_emitted_at < cutoff || row.schema_version !== TRACKER_SCHEMA_VERSION) {
        cursor.delete();
        deleted += 1;
      }
      cursor.continue();
    };
    cursorReq.onerror = () => reject(cursorReq.error ?? new Error("indexeddb purge cursor failed"));
  });
  await promisifyTx(transaction);
  return deleted;
}

/** Drop every event whose `customer_id_at_enqueue` doesn't match `currentCustomerId`. */
export async function purgeOtherIdentity(currentCustomerId: string | null): Promise<number> {
  const db = await openDb();
  const transaction = db.transaction(STORE, "readwrite");
  const store = transaction.objectStore(STORE);
  let deleted = 0;
  await new Promise<void>((resolve, reject) => {
    const cursorReq = store.openCursor();
    cursorReq.onsuccess = () => {
      const cursor = cursorReq.result;
      if (!cursor) {
        resolve();
        return;
      }
      const row = cursor.value as StoredEvent;
      if (row.customer_id_at_enqueue !== currentCustomerId) {
        cursor.delete();
        deleted += 1;
      }
      cursor.continue();
    };
    cursorReq.onerror = () => reject(cursorReq.error ?? new Error("indexeddb purge-identity cursor failed"));
  });
  await promisifyTx(transaction);
  return deleted;
}

/** Hard cap — drop the oldest events when the queue exceeds `max`. */
export async function trimToMaxSize(max: number): Promise<number> {
  const db = await openDb();
  const transaction = db.transaction(STORE, "readwrite");
  const store = transaction.objectStore(STORE);
  const total = await promisifyRequest(store.count());
  if (total <= max) {
    transaction.abort();
    return 0;
  }
  const overflow = total - max;
  const index = store.index(IDX_EMITTED_AT);
  let deleted = 0;
  await new Promise<void>((resolve, reject) => {
    const cursorReq = index.openCursor(null, "next");
    cursorReq.onsuccess = () => {
      const cursor = cursorReq.result;
      if (!cursor || deleted >= overflow) {
        resolve();
        return;
      }
      cursor.delete();
      deleted += 1;
      cursor.continue();
    };
    cursorReq.onerror = () => reject(cursorReq.error ?? new Error("indexeddb trim cursor failed"));
  });
  await promisifyTx(transaction);
  return deleted;
}

export async function countPending(): Promise<number> {
  const db = await openDb();
  return promisifyRequest(tx(db, "readonly").count());
}
