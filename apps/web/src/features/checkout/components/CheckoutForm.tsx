import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery } from "@tanstack/react-query";
import { startTransition, useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";

import { BagSkeleton } from "@/features/cart/components/BagSkeleton";
import { useCartQuery, useInvalidateCart } from "@/features/cart/useCart";
import { Context } from "@/features/events/contexts";
import { fromCartLine, variantSnapshot } from "@/features/events/payloads";
import { useSpecTrack } from "@/features/events/specEvents";
import { RecommendationRail } from "@/features/recommendations/components/RecommendationRail";
import { recommendProductsToProducts } from "@/features/recommendations/mappers";
import { apiClient } from "@/shared/api/client";
import { formatCurrency } from "@/shared/lib/format";
import { tw } from "@/shared/ui/tw";

const checkoutSchema = z.object({
  email: z.string().email(),
  fullName: z.string().min(2),
  address: z.string().min(4),
  city: z.string().min(2),
  country: z.string().min(2),
  paymentMethod: z.enum(["card", "wallet"]),
});

type CheckoutFormValues = z.infer<typeof checkoutSchema>;

type DoneState = {
  orderId: string;
  lines: { name: string; quantity: number; lineTotal: number }[];
  subtotal: number;
};

const labelSerif = "font-display text-[1.05rem] font-normal tracking-display text-ink antialiased";

const fieldLabel = `text-[0.65rem] font-semibold uppercase tracking-[0.16em] ${tw.muted}`;

const panelShell =
  "rounded-[max(var(--radius-inner),1rem)] border border-outline/35 bg-surface-strong/75 px-6 py-7 shadow-[0_1px_0_rgba(34,28,23,0.06)] ring-1 ring-inset ring-white/55 backdrop-blur-[10px] sm:px-8 sm:py-8";

const deptPillIdle =
  "min-h-10 cursor-pointer rounded-pill border border-dashed border-ink/40 bg-white/70 px-4 py-2.5 text-[0.75rem] font-medium text-ink transition-colors hover:border-ink/55 hover:bg-white";

const deptPillSelected =
  "min-h-10 cursor-pointer rounded-pill border border-ink/30 bg-surface-strong px-4 py-2.5 text-center text-[0.75rem] font-semibold text-ink shadow-[0_6px_18px_rgba(34,28,23,0.06)] ring-1 ring-inset ring-white/65 transition-colors hover:border-ink/40";

function BagOutlineIllustration() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="mx-auto h-32 w-32 text-ink/16 sm:h-36 sm:w-36"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <path
        d="M6 7h12l-1 12H7L6 7Z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M9 7V5a3 3 0 0 1 6 0v2"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function CheckoutForm() {
  const cartQuery = useCartQuery();
  const invalidateCart = useInvalidateCart();
  const trackSpec = useSpecTrack();
  const [done, setDone] = useState<DoneState | null>(null);
  const items = cartQuery.data?.items ?? [];
  const subtotal = cartQuery.data?.subtotal ?? 0;
  const ready = cartQuery.isSuccess;
  const postPurchaseContext = Context.postPurchase();
  const postPurchaseQuery = useQuery({
    queryKey: ["recommend", postPurchaseContext],
    queryFn: () => apiClient.getRecommendation(postPurchaseContext),
    enabled: done !== null,
  });

  const form = useForm<CheckoutFormValues>({
    resolver: zodResolver(checkoutSchema),
    defaultValues: {
      email: "ava@hyperpersona.demo",
      fullName: "Ava Chen",
      address: "121 Orchard Way",
      city: "Seattle",
      country: "United States",
      paymentMethod: "card",
    },
  });

  const payment = form.watch("paymentMethod");

  const mutation = useMutation({
    mutationFn: (values: CheckoutFormValues) =>
      apiClient.checkout({
        ...values,
        subtotal,
        items: items.map((line) => ({
          productId: line.productId,
          quantity: line.quantity,
        })),
      }),
    onSuccess: (response) => {
      const lines = items.map((line) => ({
        name: line.name,
        quantity: line.quantity,
        lineTotal: line.unitPrice * line.quantity,
      }));
      const st = subtotal;
      const orderId = response.orderId;
      const formValues = form.getValues();
      // Per-line `purchase` events — the recommender attributes conversions
      // to individual products. Each line stamps `order_id` so the worker
      // can group lines back into one order, plus the variant the shopper
      // picked at PDP time so per-variant conversion is observable.
      for (const line of items) {
        const variant = variantSnapshot(line.selectedOptions ?? undefined);
        trackSpec("purchase", {
          ...fromCartLine(line),
          quantity: line.quantity,
          line_total: line.unitPrice * line.quantity,
          order_id: orderId,
          ...(variant ? { variant } : {}),
        });
      }
      // Order-level summary — fires once per checkout so the worker can
      // compute basket size, mixed-category baskets, AOV per persona.
      const categories = Array.from(
        new Set(
          items
            .map((line) => fromCartLine(line).category)
            .filter((c): c is string => Boolean(c)),
        ),
      );
      trackSpec("order_placed", {
        order_id: orderId,
        subtotal: st,
        line_count: items.length,
        item_count: items.reduce((sum, line) => sum + line.quantity, 0),
        payment_method: formValues.paymentMethod,
        country: formValues.country,
        city: formValues.city,
        ...(categories.length > 0 ? { categories } : {}),
      });
      // BE clears the cart on successful checkout — invalidate so the next
      // mount fetches the now-empty state. Snapshot lines + subtotal first
      // since the confirmation view renders from the snapshot, not the
      // (about-to-be-empty) live cart.
      startTransition(() => {
        setDone({ orderId: response.orderId, lines, subtotal: st });
        invalidateCart();
      });
    },
  });

  const header = (
    <header className="max-w-3xl">
      <p className={`mb-2 text-[0.7rem] font-semibold uppercase tracking-[0.18em] ${tw.muted}`}>Checkout</p>
      <h1 className={`${tw.storyTitle} max-w-[26ch]`}>Close the loop on demo commerce.</h1>
      <p className={`mt-4 max-w-xl text-pretty text-sm leading-relaxed ${tw.muted}`}>
        No card is charged—submitting creates a fake order id so event streams and explainability surfaces can show a
        completed purchase path, consistent with the rest of the HyperPersona shell.
      </p>
    </header>
  );

  if (!ready) {
    return (
      <div className={tw.stackLg}>
        {header}
        <BagSkeleton rows={2} />
      </div>
    );
  }

  if (done) {
    return (
      <div className={`${tw.stackLg} max-w-2xl`}>
        <header className="max-w-3xl">
          <p className={`mb-2 text-[0.7rem] font-semibold uppercase tracking-[0.18em] ${tw.muted}`}>Checkout</p>
          <h1 className={`${tw.storyTitle} max-w-[20ch]`}>You&apos;re all set.</h1>
          <p className={`mt-4 max-w-xl text-sm leading-relaxed ${tw.muted}`}>
            Demo order recorded—head back to the catalog or open your bag to keep exploring the storefront.
          </p>
        </header>
        <section className={`${panelShell} ${tw.stackMd}`}>
          <p className={`text-[0.65rem] font-semibold uppercase tracking-[0.2em] ${tw.muted}`}>Order confirmed</p>
          <h2 className={`${tw.displayH2} text-[clamp(1.5rem,3vw,2rem)] font-medium leading-snug`}>Thank you—demo order placed</h2>
          <p className={`text-sm leading-relaxed ${tw.muted}`}>
            Reference <span className="font-medium text-ink/90">{done.orderId}</span>. Use this id in the trace panel to
            narrate post-checkout personalization.
          </p>
          <ul className="m-0 grid list-none gap-3 border-t border-outline/20 pt-5" role="list">
            {done.lines.map((line) => (
              <li key={`${line.name}-${line.quantity}`} className="flex justify-between gap-4 text-sm text-ink/90">
                <span className="min-w-0 text-pretty">
                  {line.name}
                  <span className={`${tw.muted}`}> ×{line.quantity}</span>
                </span>
                <span className="shrink-0 tabular-nums font-medium">{formatCurrency(line.lineTotal)}</span>
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap justify-between gap-4 border-t border-outline/20 pt-5 text-sm">
            <span className={`font-semibold uppercase tracking-ui-wide ${tw.muted}`}>Total</span>
            <span className="font-display text-xl font-medium tabular-nums text-ink">{formatCurrency(done.subtotal)}</span>
          </div>
        </section>
        <div className="flex flex-wrap gap-4">
          <Link to="/catalog" className={tw.buttonEditorialBag}>
            Browse catalog
          </Link>
          <Link to="/cart" className={tw.buttonGhost}>
            View bag
          </Link>
        </div>

        {postPurchaseQuery.data && postPurchaseQuery.data.products.length > 0 ? (
          <RecommendationRail
            products={recommendProductsToProducts(postPurchaseQuery.data.products)}
            sourceContext={postPurchaseContext}
            title="Worth considering for next time"
            subtitle="Curated for you"
            reason={postPurchaseQuery.data.personalization_reason ?? undefined}
            personalized={Boolean(postPurchaseQuery.data.personalization_reason)}
            presentation="default"
          />
        ) : null}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className={`${tw.stackLg} min-h-[min(52vh,560px)]`}>
        {header}
        <div className="flex flex-col items-center gap-8 py-12 text-center sm:gap-10 sm:py-16" aria-live="polite">
          <BagOutlineIllustration />
          <div className="max-w-md">
            <h2 className={`${tw.displayH2} text-2xl sm:text-[1.65rem]`}>Nothing to check out</h2>
            <p className={`mt-3 text-sm leading-relaxed ${tw.muted}`}>
              Your bag is empty. Add products from the catalog, then return here to run the fake checkout and emit a
              completed order event.
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-4">
              <Link to="/catalog" className={tw.buttonEditorialBag}>
                Browse catalog
              </Link>
              <Link to="/cart" className={tw.buttonGhost}>
                Open bag
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const showFieldErrors = form.formState.isSubmitted;

  return (
    <div className={tw.stackLg}>
      {header}

      <div className="grid gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)] lg:items-start lg:gap-x-14 xl:gap-x-16">
        <form
          className={`${tw.stackLg} max-w-2xl`}
          onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
          noValidate
        >
          <section className={`${tw.stackMd}`}>
            <h3 className={labelSerif}>Contact</h3>
            <div className="grid gap-5 sm:grid-cols-2">
              <label className="grid gap-2">
                <span className={fieldLabel}>Email</span>
                <input autoComplete="email" spellCheck={false} className={tw.fieldInput} {...form.register("email")} />
                {showFieldErrors && form.formState.errors.email ? (
                  <span className="text-xs text-red-800/90">{form.formState.errors.email.message}</span>
                ) : null}
              </label>
              <label className="grid gap-2">
                <span className={fieldLabel}>Full name</span>
                <input autoComplete="name" className={tw.fieldInput} {...form.register("fullName")} />
                {showFieldErrors && form.formState.errors.fullName ? (
                  <span className="text-xs text-red-800/90">{form.formState.errors.fullName.message}</span>
                ) : null}
              </label>
            </div>
          </section>

          <section className={`${tw.stackMd} border-t border-outline/15 pt-8`}>
            <h3 className={labelSerif}>Shipping</h3>
            <div className="grid gap-5">
              <label className="grid gap-2">
                <span className={fieldLabel}>Street address</span>
                <input autoComplete="street-address" className={tw.fieldInput} {...form.register("address")} />
                {showFieldErrors && form.formState.errors.address ? (
                  <span className="text-xs text-red-800/90">{form.formState.errors.address.message}</span>
                ) : null}
              </label>
              <div className="grid gap-5 sm:grid-cols-2">
                <label className="grid gap-2">
                  <span className={fieldLabel}>City</span>
                  <input autoComplete="address-level2" className={tw.fieldInput} {...form.register("city")} />
                  {showFieldErrors && form.formState.errors.city ? (
                    <span className="text-xs text-red-800/90">{form.formState.errors.city.message}</span>
                  ) : null}
                </label>
                <label className="grid gap-2">
                  <span className={fieldLabel}>Country</span>
                  <input autoComplete="country-name" className={tw.fieldInput} {...form.register("country")} />
                  {showFieldErrors && form.formState.errors.country ? (
                    <span className="text-xs text-red-800/90">{form.formState.errors.country.message}</span>
                  ) : null}
                </label>
              </div>
            </div>
          </section>

          <section className={`${tw.stackMd} border-t border-outline/15 pt-8`}>
            <h3 className={labelSerif}>Payment</h3>
            <p className={`text-sm ${tw.muted}`}>Choose a method for the demo—no credentials are collected.</p>
            <div className="flex flex-wrap gap-2" role="group" aria-label="Payment method">
              <button
                type="button"
                className={payment === "card" ? deptPillSelected : deptPillIdle}
                aria-pressed={payment === "card"}
                onClick={() => form.setValue("paymentMethod", "card", { shouldValidate: true, shouldDirty: true })}
              >
                Card
              </button>
              <button
                type="button"
                className={payment === "wallet" ? deptPillSelected : deptPillIdle}
                aria-pressed={payment === "wallet"}
                onClick={() => form.setValue("paymentMethod", "wallet", { shouldValidate: true, shouldDirty: true })}
              >
                Wallet
              </button>
            </div>
            <input type="hidden" {...form.register("paymentMethod")} />
          </section>

          {mutation.isError ? (
            <p className="text-sm text-red-800/90" role="alert">
              Checkout could not complete. Try again in a moment.
            </p>
          ) : null}
          <div className="flex flex-wrap gap-4 border-t border-outline/15 pt-8">
            <button type="submit" className={tw.buttonEditorialBag} disabled={mutation.isPending}>
              {mutation.isPending ? "Placing order…" : "Place demo order"}
            </button>
            <Link to="/cart" className={tw.buttonGhost}>
              Back to bag
            </Link>
          </div>
        </form>

        <aside className={`${panelShell} ${tw.stackMd} lg:sticky lg:top-28`}>
          <p className={`text-[0.65rem] font-semibold uppercase tracking-[0.2em] ${tw.muted}`}>Order summary</p>
          <ul className="m-0 grid list-none gap-3 p-0" role="list">
            {items.map((line) => (
              <li key={line.productId} className="flex justify-between gap-3 text-sm leading-snug text-ink/88">
                <span className="min-w-0 text-pretty">
                  {line.name}
                  <span className={`${tw.muted}`}> ×{line.quantity}</span>
                </span>
                <span className="shrink-0 tabular-nums font-medium text-ink">
                  {formatCurrency(line.unitPrice * line.quantity)}
                </span>
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap justify-between gap-3 border-t border-outline/20 pt-5 text-sm">
            <span className={`font-semibold uppercase tracking-ui-wide ${tw.muted}`}>Subtotal</span>
            <span className="font-display text-lg font-medium tabular-nums text-ink">{formatCurrency(subtotal)}</span>
          </div>
        </aside>
      </div>
    </div>
  );
}
