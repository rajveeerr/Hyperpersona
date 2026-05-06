import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { prefetchProductPageChunk } from "@/app/routeChunks";
import { CatalogProductGridSkeleton } from "@/features/catalog/components/CatalogSkeletons";
import { Context } from "@/features/events/contexts";
import { useOrdersQuery } from "@/features/orders/useOrders";
import { RecommendationRail } from "@/features/recommendations/components/RecommendationRail";
import { recommendProductsToProducts } from "@/features/recommendations/mappers";
import { resolveRailCopy } from "@/features/recommendations/railCopy";
import { apiClient } from "@/shared/api/client";
import type { OrderLine, OrderSummary } from "@/shared/api/contracts";
import { formatCurrency } from "@/shared/lib/format";
import { tw } from "@/shared/ui/tw";

const STATUS_LABELS: Record<OrderSummary["status"], string> = {
  placed: "Placed",
  processing: "Processing",
  shipped: "Shipped",
  delivered: "Delivered",
  cancelled: "Cancelled",
};

function OrdersEmptyIllustration() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-36 w-36 shrink-0 text-ink/16 sm:h-40 sm:w-40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <path
        d="M3 7h18l-1.5 13.5a1 1 0 0 1-1 .9H5.5a1 1 0 0 1-1-.9L3 7Z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M8 7V5a4 4 0 0 1 8 0v2"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function formatOrderDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function OrderLineRow({ line }: { line: OrderLine }) {
  return (
    <li className="flex items-baseline justify-between gap-4 text-[0.85rem] leading-relaxed text-ink/80">
      <Link
        to={`/products/${line.slug}`}
        prefetch="intent"
        onMouseEnter={prefetchProductPageChunk}
        onFocus={prefetchProductPageChunk}
        className="min-w-0 flex-1 truncate text-ink underline decoration-ink/20 underline-offset-[0.22em] transition-colors hover:text-accent-strong"
      >
        {line.name}
      </Link>
      <span className={`shrink-0 text-[0.75rem] ${tw.muted}`}>×{line.quantity}</span>
      <span className="shrink-0 tabular-nums text-ink">
        {formatCurrency(line.unitPrice * line.quantity)}
      </span>
    </li>
  );
}

function OrderCard({ order }: { order: OrderSummary }) {
  const statusLabel = STATUS_LABELS[order.status] ?? order.status;
  const lines = order.lines ?? [];
  return (
    <article className="flex flex-col gap-5 border-b border-[#e5e5e5] px-4 py-7 sm:px-6 sm:py-8">
      <header className="flex flex-wrap items-baseline justify-between gap-3">
        <div className="min-w-0">
          <p className={`text-[0.65rem] font-semibold uppercase tracking-[0.16em] ${tw.muted}`}>
            Order {order.id}
          </p>
          <h3 className="mt-1 text-[1rem] font-medium text-ink sm:text-[1.0625rem]">
            Placed {formatOrderDate(order.placedAt)} · {order.lineCount}{" "}
            {order.lineCount === 1 ? "item" : "items"}
          </h3>
        </div>
        <div className="flex shrink-0 items-baseline gap-3">
          <span className={`${tw.chip} text-[0.7rem]`}>{statusLabel}</span>
          <span className="text-[0.95rem] font-medium tabular-nums text-ink sm:text-[1rem]">
            {formatCurrency(order.total)}
          </span>
        </div>
      </header>

      {lines.length > 0 ? (
        <ul className="m-0 flex list-none flex-col gap-2 p-0" role="list">
          {lines.map((line) => (
            <OrderLineRow key={line.productId} line={line} />
          ))}
        </ul>
      ) : null}

      <footer className={`flex flex-wrap items-baseline justify-between gap-3 text-[0.8rem] ${tw.muted}`}>
        <span className="truncate">Shipping to {order.destinationLabel}</span>
        {order.trackingUrl ? (
          <a
            href={order.trackingUrl}
            target="_blank"
            rel="noreferrer"
            className={tw.linkCommerceUnderline}
          >
            Track shipment
          </a>
        ) : null}
      </footer>
    </article>
  );
}

export function OrdersPage() {
  const ordersQuery = useOrdersQuery();

  const items = ordersQuery.data?.items ?? [];
  const ready = ordersQuery.isSuccess;
  const hasItems = items.length > 0;
  const ordersContext = Context.orders();
  const recommendationsQuery = useQuery({
    queryKey: ["recommend", ordersContext],
    queryFn: () => apiClient.getRecommendation(ordersContext),
    enabled: ready,
  });

  return (
    <div
      className={`${tw.stackLg} min-h-[min(76vh,880px)] pt-8 sm:pt-10 lg:pt-12 pb-12 sm:pb-14 lg:pb-16`}
    >
      <header className="max-w-3xl">
        <p className={`mb-2 text-[0.7rem] font-semibold uppercase tracking-[0.18em] ${tw.muted}`}>
          Orders
        </p>
        <h1 className={`${tw.storyTitle} max-w-[26ch]`}>Your purchase history, ready to revisit.</h1>
        <p className={`mt-4 max-w-xl text-pretty text-sm leading-relaxed ${tw.muted}`}>
          Past orders inform reorder rails and post-purchase recommendations. Tap any line to jump
          back to the product.
        </p>
      </header>

      {ordersQuery.isError ? (
        <p className="text-sm text-red-800/90" role="alert">
          Could not load your orders. Check your connection and try again.
        </p>
      ) : !ready ? (
        <div aria-busy aria-label="Loading orders">
          <CatalogProductGridSkeleton count={4} />
        </div>
      ) : hasItems ? (
        <ul
          className="m-0 flex list-none flex-col border-t border-[#e5e5e5] p-0"
          role="list"
        >
          {items.map((order) => (
            <li key={order.id}>
              <OrderCard order={order} />
            </li>
          ))}
        </ul>
      ) : (
        <div
          className="flex flex-1 flex-col items-center justify-center gap-8 py-14 text-center sm:gap-10 sm:py-20"
          aria-live="polite"
        >
          <OrdersEmptyIllustration />
          <div className="max-w-md">
            <h2 className={`${tw.displayH2} text-2xl sm:text-[1.65rem]`}>No orders yet</h2>
            <p className={`mt-3 text-sm leading-relaxed ${tw.muted}`}>
              Once you place an order it will land here, and the recommendations below will start
              leaning on your purchase signals.
            </p>
            <Link to="/catalog" className={`mt-8 inline-flex ${tw.buttonEditorialBag}`}>
              Browse catalog
            </Link>
          </div>
        </div>
      )}

      {ready && recommendationsQuery.data && recommendationsQuery.data.products.length > 0
        ? (() => {
            const rail = resolveRailCopy(recommendationsQuery.data, {
              eyebrow: "Because you ordered",
              headline: hasItems ? "Reorder essentials and pairings" : "Trending picks to start with",
              subtitle: hasItems
                ? "Tuned to what you've already bought — restock or complement."
                : "Editor-curated picks while your order history fills in.",
              modeLabel: hasItems ? "Reorder & pairings" : "Trending now",
            });
            return (
              <RecommendationRail
                products={recommendProductsToProducts(recommendationsQuery.data.products)}
                sourceContext={ordersContext}
                title={rail.headline}
                subtitle={rail.eyebrow}
                reason={rail.subtitle}
                personalized={Boolean(recommendationsQuery.data.personalization_reason)}
                modeLabel={rail.mode_label}
                presentation="default"
              />
            );
          })()
        : null}
    </div>
  );
}
