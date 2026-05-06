import { motion, useReducedMotion } from "framer-motion";

import type { Product } from "@/shared/api/contracts";

import { ProductCard } from "@/features/catalog/components/ProductCard";

/**
 * 1px hairlines without a slab fill: **top + left** on the shell, **right + bottom** on each cell
 * (table-grid trick). `#e5e5e5` matches `EditorialNewCollectionSection` dividers—barely-there on cream and white.
 */
const catalogGridLine = "border-[#e5e5e5]";

const catalogGridShellCore = `grid grid-cols-1 gap-0 border-l border-t ${catalogGridLine} lg:grid-cols-3`;

/** `<ul>` — list reset + shell borders. */
export const catalogGridShellListClass = `m-0 list-none p-0 ${catalogGridShellCore}`;

/** Plain `<div>` skeleton wrapper (same lattice as the list). */
export const catalogGridShellDivClass = catalogGridShellCore;

/** Every cell: completes internal verticals and horizontals; outer frame from shell top/left. */
export const catalogGridCellEdgeClass = `border-r border-b ${catalogGridLine}`;

/** Skeleton / motion cell — layout only, transparent; pair with `catalogGridCellEdgeClass`. */
export const catalogTileCell =
  "flex min-h-52 items-center justify-center px-4 py-8 sm:min-h-56 sm:px-6 sm:py-10 lg:px-7 lg:py-12";

/** Smaller PDP suggestions skeleton cells. */
export const catalogSuggestionsCell =
  "flex min-h-40 items-center justify-center px-3 py-6 sm:min-h-44 sm:px-4 sm:py-8";

const catalogTileMotionLayout = `${catalogTileCell} ${catalogGridCellEdgeClass}`;

type ProductGridProps = {
  products: Product[];
  /** Passed to `ProductCard` when the rail should explain why tiles appear (search, recommendations). */
  accent?: string;
  /** Forwarded to each `ProductCard` — used by recommendation rails for `recommendation_clicked`. */
  onProductClick?: (product: Product) => void;
};

function CatalogGridMotionItem({
  product,
  accent,
  reduced,
  onProductClick,
}: {
  product: Product;
  accent?: string;
  reduced: boolean;
  onProductClick?: (product: Product) => void;
}) {
  return (
    <motion.li
      className={catalogTileMotionLayout}
      style={{ transformOrigin: "50% 50%" }}
      initial={false}
      animate={{ scale: 1 }}
      whileHover={{ scale: reduced ? 1 : 1.015 }}
      whileTap={reduced ? undefined : { scale: 0.988 }}
      transition={
        reduced
          ? { duration: 0.22, ease: [0.22, 1, 0.36, 1] }
          : { type: "spring", stiffness: 400, damping: 22, mass: 0.58 }
      }
    >
      <ProductCard product={product} accent={accent} onClick={onProductClick} />
    </motion.li>
  );
}

/** Transparent 3-up lattice + `ProductCard` — inherits parent background. */
export function ProductGrid({ products, accent, onProductClick }: ProductGridProps) {
  const reduced = useReducedMotion() ?? false;
  return (
    <ul className={catalogGridShellListClass} role="list">
      {products.map((product) => (
        <CatalogGridMotionItem
          key={product.id}
          product={product}
          accent={accent}
          reduced={reduced}
          onProductClick={onProductClick}
        />
      ))}
    </ul>
  );
}
