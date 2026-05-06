import { PdpDetailTabPanels } from "@/features/catalog/components/pdp/PdpDetailTabPanels";
import {
  optionIdle,
  optionSelected,
  tabPill,
  type DetailTab,
} from "@/features/catalog/components/pdp/pdpShared";
import type { Product } from "@/shared/api/contracts";
import { tw } from "@/shared/ui/tw";

type PdpTabbedDetailsProps = {
  product: Product;
  vertical: string;
  tab: DetailTab;
  tabs: { id: DetailTab; label: string }[];
  specLines: string[];
  emitTab: (next: DetailTab) => void;
  onReportProduct: () => void;
};

export function PdpTabbedDetails({
  product,
  vertical,
  tab,
  tabs,
  specLines,
  emitTab,
  onReportProduct,
}: PdpTabbedDetailsProps) {
  return (
    <div className="mt-10 border-t border-outline/15 pt-8 sm:mt-12 sm:pt-10">
      <div className="mb-6 flex flex-col gap-4 sm:mb-8 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
        <div className="flex flex-wrap gap-2" role="tablist" aria-label="Product detail sections">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              className={`${tabPill} ${tab === t.id ? optionSelected : optionIdle}`}
              onClick={() => emitTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>
        <button
          type="button"
          className={`shrink-0 self-start text-left text-[0.6875rem] font-semibold uppercase tracking-ui-wide text-ink/70 underline decoration-ink/25 underline-offset-[0.35rem] transition-colors hover:text-ink sm:self-center`}
          onClick={onReportProduct}
        >
          Report product
        </button>
      </div>

      <PdpDetailTabPanels product={product} vertical={vertical} tab={tab} specLines={specLines} />
    </div>
  );
}
