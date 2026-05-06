import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";

import { AuthShell } from "@/features/auth/AuthShell";
import { authFieldLabel } from "@/features/auth/styles";
import { useAuth } from "@/features/auth/useAuth";
import { apiClient } from "@/shared/api/client";
import { ApiError, type ConsentRecord } from "@/shared/api/contracts";
import { tw } from "@/shared/ui/tw";

// Backend rule: password.min_length=8 (see RegisterRequest in shared/schemas.py).
const registerSchema = z
  .object({
    email: z.string().email("Enter a valid email"),
    password: z.string().min(8, "Use at least 8 characters"),
    confirmPassword: z.string(),
    consentAnalytics: z.boolean(),
    consentPersonalization: z.boolean(),
    consentMarketing: z.boolean(),
  })
  .refine((value) => value.password === value.confirmPassword, {
    message: "Passwords don't match",
    path: ["confirmPassword"],
  });

type RegisterValues = z.infer<typeof registerSchema>;

type LocationState = { from?: string } | null;

const SCOPE_COPY = {
  analytics: "Analytics — funnel + trace metrics. Lets the demo show what events fired.",
  personalization: "Personalization — search ranking, rails, and reasons sharpen as you browse.",
  marketing: "Marketing — reserved for lifecycle messaging in a full rollout.",
} as const;

export function RegisterPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const { register: registerAccount } = useAuth();

  const form = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      email: "",
      password: "",
      confirmPassword: "",
      consentAnalytics: true,
      consentPersonalization: true,
      consentMarketing: false,
    },
  });

  const mutation = useMutation({
    mutationFn: async (values: RegisterValues) => {
      const session = await registerAccount({ email: values.email, password: values.password });
      // Save the consent record immediately so the event tracker's
      // `personalization`-scope gate opens on the very first render after
      // signup. See `tracker.ts:147-151` for the gate.
      const scopes = (
        [
          values.consentAnalytics ? "analytics" : null,
          values.consentPersonalization ? "personalization" : null,
          values.consentMarketing ? "marketing" : null,
        ].filter(Boolean) as string[]
      );
      let consentRecord: ConsentRecord | null = null;
      try {
        consentRecord = await apiClient.updateConsent(scopes);
      } catch (err) {
        // Non-fatal — surface to the dev console so a real save failure
        // doesn't go silent, and let the floating ConsentBanner pick up
        // the slack on the next page load.
        console.warn(
          "[register] consent POST failed; the consent banner will surface on next mount",
          err,
        );
      }
      return { session, consentRecord };
    },
    onSuccess: ({ session, consentRecord }) => {
      // Don't blow away the cache wholesale — `queryClient.clear()` would
      // discard the consent record we just saved, forcing a fresh
      // `GET /consent` from `useConsentQuery`. That GET races against the
      // POST and lands first with a 404 because `setSession` already
      // re-keyed `useConsentQuery` to the new customerId before our POST
      // reached the BE. Selectively drop identity-scoped caches everywhere
      // EXCEPT the consent namespace, then prime the consent cache with
      // the record we just received so the bridge + banner read from
      // memory instead of racing the network.
      queryClient.removeQueries({
        predicate: (query) => query.queryKey[0] !== "consent",
      });
      if (consentRecord) {
        queryClient.setQueryData(["consent", session.customerId], consentRecord);
      }
      const state = location.state as LocationState;
      navigate(state?.from ?? "/", { replace: true });
    },
  });

  const showFieldErrors = form.formState.isSubmitted;

  function formError(): string | null {
    if (!mutation.isError) return null;
    const err = mutation.error;
    if (err instanceof ApiError) {
      if (err.status === 409) return "That email is already registered. Try signing in instead.";
      if (err.status === 422) return "Check your email and password and try again.";
      if (err.status === 0) return "Network error — check your connection.";
      return err.message;
    }
    return "Could not create your account. Try again in a moment.";
  }

  return (
    <AuthShell
      eyebrow="Create account"
      title="Make HyperPersona yours."
      intro="Create an account to keep consent, profile, and recommendation history tied to you across sessions."
      altPrompt={{ text: "Already have an account?", linkLabel: "Sign in", to: "/login" }}
      submitLabel="Create account"
      busy={mutation.isPending}
      formError={formError()}
      onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
    >
      <label className="grid gap-2">
        <span className={authFieldLabel}>Email</span>
        <input
          type="email"
          autoComplete="email"
          spellCheck={false}
          className={tw.fieldInput}
          {...form.register("email")}
        />
        {showFieldErrors && form.formState.errors.email ? (
          <span className="text-xs text-red-800/90">{form.formState.errors.email.message}</span>
        ) : null}
      </label>

      <label className="grid gap-2">
        <span className={authFieldLabel}>Password</span>
        <input
          type="password"
          autoComplete="new-password"
          className={tw.fieldInput}
          {...form.register("password")}
        />
        {showFieldErrors && form.formState.errors.password ? (
          <span className="text-xs text-red-800/90">{form.formState.errors.password.message}</span>
        ) : null}
        <span className={`text-xs ${tw.muted}`}>At least 8 characters.</span>
      </label>

      <label className="grid gap-2">
        <span className={authFieldLabel}>Confirm password</span>
        <input
          type="password"
          autoComplete="new-password"
          className={tw.fieldInput}
          {...form.register("confirmPassword")}
        />
        {showFieldErrors && form.formState.errors.confirmPassword ? (
          <span className="text-xs text-red-800/90">{form.formState.errors.confirmPassword.message}</span>
        ) : null}
      </label>

      <fieldset className="grid gap-3 border-t border-outline/15 pt-5">
        <legend className={authFieldLabel}>Personalization preferences</legend>
        <p className={`text-xs leading-relaxed ${tw.muted}`}>
          Pick what the demo may use. You can change these any time at <code className="font-mono text-[0.7rem]">/consent</code>.
        </p>

        <label className="flex cursor-pointer items-start gap-3 py-1">
          <input
            type="checkbox"
            className="mt-0.75 size-4 shrink-0 rounded border border-outline accent-ink"
            {...form.register("consentAnalytics")}
          />
          <span className="text-sm leading-snug text-ink/88">{SCOPE_COPY.analytics}</span>
        </label>

        <label className="flex cursor-pointer items-start gap-3 py-1">
          <input
            type="checkbox"
            className="mt-0.75 size-4 shrink-0 rounded border border-outline accent-ink"
            {...form.register("consentPersonalization")}
          />
          <span className="text-sm leading-snug text-ink/88">{SCOPE_COPY.personalization}</span>
        </label>

        <label className="flex cursor-pointer items-start gap-3 py-1">
          <input
            type="checkbox"
            className="mt-0.75 size-4 shrink-0 rounded border border-outline accent-ink"
            {...form.register("consentMarketing")}
          />
          <span className="text-sm leading-snug text-ink/88">{SCOPE_COPY.marketing}</span>
        </label>
      </fieldset>
    </AuthShell>
  );
}
