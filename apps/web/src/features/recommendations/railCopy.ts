import type { RecommendRailCopy, RecommendResponse } from "@/shared/api/contracts";

/**
 * Per-callsite fallback used when the BE response doesn't ship `rail` —
 * e.g., a worker pinned to a pre-`rail` build, or a non-`/recommend`
 * surface that wants the same rail layout. Mirrors `RecommendRailCopy`
 * but with `modeLabel` (camelCase) since callers pass it that way.
 */
export type RailCopyFallback = {
  eyebrow: string;
  headline: string;
  subtitle: string;
  modeLabel?: string;
};

/**
 * Read rail copy from a /recommend response with a guaranteed shape.
 *
 * Prefers BE-driven copy (the v2 worker bakes context + dominant
 * category into the headline). When `rail` is missing, falls back to
 * the static copy each surface used to hardcode — and still threads
 * `personalization_reason` into the subtitle so the rail header reads
 * "Because you …" whenever the BE produced a Prefers fact, even on the
 * fallback path.
 *
 * `data` accepts the broader response shape so callers can pass
 * `recommendationsQuery.data` without narrowing first.
 */
export function resolveRailCopy(
  data:
    | (Pick<RecommendResponse, "personalization_reason"> & {
        rail?: RecommendRailCopy;
      })
    | undefined
    | null,
  fallback: RailCopyFallback,
): RecommendRailCopy {
  if (data?.rail) return data.rail;

  const personalized = Boolean(data?.personalization_reason);
  return {
    eyebrow: fallback.eyebrow,
    headline: fallback.headline,
    subtitle: data?.personalization_reason ?? fallback.subtitle,
    mode_label: personalized ? null : fallback.modeLabel ?? null,
  };
}
