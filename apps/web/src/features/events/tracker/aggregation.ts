/**
 * Cheap, in-memory dedupe so we don't enqueue the same event twice in <2s
 * (per `event-types-description.md` §1 aggregation rules). Keyed on
 * `event_type` plus a stable JSON hash of the payload.
 *
 * Why hash here instead of comparing the JSON string directly: keeps the
 * memory footprint bounded and makes the cache cheap to LRU-trim.
 *
 * Per-PDP `product_dwell` and search-on-submit-only are enforced at the
 * call site (PDP timer, search form `onSubmit`). The window-dedupe is the
 * generic safety net for hot paths like a user double-clicking a tile.
 */

const DEDUPE_WINDOW_MS = 2_000;
const MAX_KEYS = 200;

const recent = new Map<string, number>();

function fnv1a(input: string): string {
  // 32-bit FNV-1a — good enough for collision-free local dedupe over the
  // small set of recent payload shapes; not used for anything cryptographic.
  let h = 0x811c9dc5;
  for (let i = 0; i < input.length; i += 1) {
    h ^= input.charCodeAt(i);
    h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) >>> 0;
  }
  return h.toString(16);
}

function stableStringify(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")}]`;
  const entries = Object.entries(value as Record<string, unknown>).sort(([a], [b]) => a.localeCompare(b));
  return `{${entries.map(([k, v]) => `${JSON.stringify(k)}:${stableStringify(v)}`).join(",")}}`;
}

function trim(now: number): void {
  if (recent.size <= MAX_KEYS) return;
  for (const [key, ts] of recent) {
    if (now - ts > DEDUPE_WINDOW_MS) recent.delete(key);
    if (recent.size <= MAX_KEYS) break;
  }
}

/**
 * @returns true when this event_type+payload combo was seen <2s ago and the
 *          caller should drop it; otherwise records the timestamp and
 *          returns false.
 */
export function shouldDropAsDuplicate(eventType: string, payload: Record<string, unknown>): boolean {
  const now = Date.now();
  const key = `${eventType}::${fnv1a(stableStringify(payload))}`;
  const prev = recent.get(key);
  if (prev !== undefined && now - prev < DEDUPE_WINDOW_MS) return true;
  recent.set(key, now);
  trim(now);
  return false;
}

/** Test/debug-only — clears the dedupe cache. */
export function _resetDedupeWindow(): void {
  recent.clear();
}
