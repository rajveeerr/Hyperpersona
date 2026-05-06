import { CheckoutForm } from "@/features/checkout/components/CheckoutForm";
import { tw } from "@/shared/ui/tw";

export function CheckoutPage() {
  return (
    <div className={`${tw.stackLg} min-h-[min(76vh,880px)] pt-8 sm:pt-10 lg:pt-12 pb-12 sm:pb-14 lg:pb-16`}>
      <CheckoutForm />
    </div>
  );
}
