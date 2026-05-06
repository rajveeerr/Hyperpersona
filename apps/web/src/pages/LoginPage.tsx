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

const loginSchema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(1, "Enter your password"),
});

type LoginValues = z.infer<typeof loginSchema>;

type LocationState = { from?: string } | null;

export function LoginPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();

  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const mutation = useMutation({
    mutationFn: (values: LoginValues) => login(values),
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
      if (err.status === 401) return "That email and password don't match. Try again.";
      if (err.status === 0) return "Network error — check your connection.";
      return err.message;
    }
    return "Could not sign in. Try again in a moment.";
  }

  return (
    <AuthShell
      eyebrow="Sign in"
      title="Welcome back."
      intro="Sign in to sync personalization, recommendations, and consent across this device."
      altPrompt={{ text: "New here?", linkLabel: "Create an account", to: "/register" }}
      submitLabel="Sign in"
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
          autoComplete="current-password"
          className={tw.fieldInput}
          {...form.register("password")}
        />
        {showFieldErrors && form.formState.errors.password ? (
          <span className="text-xs text-red-800/90">{form.formState.errors.password.message}</span>
        ) : null}
      </label>
    </AuthShell>
  );
}
