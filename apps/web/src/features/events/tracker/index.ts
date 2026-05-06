export { initEventTracker } from "@/features/events/tracker/init";
export {
  trackEvent,
  flushPending,
  setConsentSnapshot,
  getConsentSnapshot,
  clearTrackerQueue,
} from "@/features/events/tracker/tracker";
export type { TrackInput } from "@/features/events/tracker/types";
