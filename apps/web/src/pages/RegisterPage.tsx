import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";

import { AuthShell } from "@/features/auth/AuthShell";
import { authFieldLabel } from "@/features/auth/styles";
import { useAuth } from "@/features/auth/useAuth";
import { ApiError } from "@/shared/api/contracts";
import { tw } from "@/shared/ui/tw";

// Backend rule: password.min_length=8 (see RegisterRequest in shared/schemas.py).
const registerSchema = z
  .object({
    email: z.string().email("Enter a valid email"),
    password: z.string().min(8, "Use at least 8 characters"),
    confirmPassword: z.string(),
  })
  .refine((value) => value.password === value.confirmPassword, {
    message: "Passwords don't match",
    path: ["confirmPassword"],
  });

type RegisterValues = z.infer<typeof registerSchema>;

type LocationState = { from?: string } | null;

export function RegisterPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const { register: registerAccount } = useAuth();

  const form = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { email: "", password: "", confirmPassword: "" },
  });

  const mutation = useMutation({
    mutationFn: (values: RegisterValues) =>
      registerAccount({ email: values.email, password: values.password }),
    onSuccess: () => {
      queryClient.clear();
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
    </AuthShell>
  );
}
