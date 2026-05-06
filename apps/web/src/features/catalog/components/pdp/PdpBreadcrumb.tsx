import { Link } from "react-router-dom";

import { prefetchCatalogPageChunk } from "@/app/routeChunks";
import { formatCategoryLabel } from "@/features/catalog/components/pdp/pdpShared";
import type { Product } from "@/shared/api/contracts";
import { tw } from "@/shared/ui/tw";

type PdpBreadcrumbProps = {
  product: Pick<Product, "category" | "name">;
};

export function PdpBreadcrumb({ product }: PdpBreadcrumbProps) {
  return (
    <nav className={`mb-8 flex flex-wrap gap-x-2 gap-y-1 text-[0.75rem] ${tw.muted}`} aria-label="Breadcrumb">
      <Link to="/" className="underline decoration-ink/25 underline-offset-2 hover:text-ink">
        Home
      </Link>
      <span aria-hidden>/</span>
      <Link
        to="/catalog"
        prefetch="intent"
        className="underline decoration-ink/25 underline-offset-2 hover:text-ink"
        onMouseEnter={prefetchCatalogPageChunk}
        onFocus={prefetchCatalogPageChunk}
      >
        Catalog
      </Link>
      <span aria-hidden>/</span>
      <Link
        to={`/catalog?category=${encodeURIComponent(product.category)}`}
        prefetch="intent"
        className="underline decoration-ink/25 underline-offset-2 hover:text-ink"
        onMouseEnter={prefetchCatalogPageChunk}
        onFocus={prefetchCatalogPageChunk}
      >
        {formatCategoryLabel(product.category)}
      </Link>
      <span aria-hidden>/</span>
      <span className="max-w-[min(100%,28rem)] truncate text-ink/80">{product.name}</span>
    </nav>
  );
}
