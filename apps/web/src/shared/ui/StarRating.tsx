/**
 * Five-point stars with fractional fill (0–5 scale). Empty shell uses muted ink; fill uses accent terracotta.
 */

function StarSegment({ fill }: { fill: number }) {
  const clamped = Math.min(1, Math.max(0, fill));
  return (
    <span className="relative inline-block h-[1em] w-[1em] shrink-0">
      {/* Empty */}
      <svg
        className="absolute inset-0 block h-full w-full text-ink/18"
        viewBox="0 0 20 20"
        fill="currentColor"
        aria-hidden
      >
        <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
      </svg>
      {/* Filled portion */}
      <span className="absolute inset-0 overflow-hidden" style={{ width: `${clamped * 100}%` }}>
        <svg
          className="block h-[1em] w-[1em] shrink-0 text-accent-strong"
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden
        >
          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
        </svg>
      </span>
    </span>
  );
}

type StarRatingProps = {
  rating: number;
  /** Stars inherit font-size; set `text-sm` / `text-[0.8125rem]` etc. on this wrapper */
  className?: string;
};

export function StarRating({ rating, className }: StarRatingProps) {
  const r = Math.min(5, Math.max(0, rating));
  const label = `${r.toFixed(1)} out of 5 stars`;

  return (
    <span
      className={`inline-flex items-center gap-px ${className ?? ""}`}
      role="img"
      aria-label={label}
    >
      {[0, 1, 2, 3, 4].map((i) => (
        <StarSegment key={i} fill={Math.min(1, Math.max(0, r - i))} />
      ))}
    </span>
  );
}
