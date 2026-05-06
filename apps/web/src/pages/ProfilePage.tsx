import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { useAuth } from "@/features/auth/useAuth";
import { ProfileLabSkeleton } from "@/features/profile/components/ProfileLabSkeleton";
import { ProfileSummary } from "@/features/profile/components/ProfileSummary";
import { useTrackEvent } from "@/features/events/useTrackEvent";
import { clearTrackerQueue } from "@/features/events/tracker";
import { apiClient } from "@/shared/api/client";
import { ApiError } from "@/shared/api/contracts";
import { tw } from "@/shared/ui/tw";

export function ProfilePage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { logout } = useAuth();
  const track = useTrackEvent();
  const [deleteArmed, setDeleteArmed] = useState(false);
  const profileQuery = useQuery({
    queryKey: ["profile"],
    queryFn: apiClient.getProfile,
  });
  const explanationsQuery = useQuery({
    queryKey: ["explanations"],
    queryFn: apiClient.getExplanations,
  });

  const mutation = useMutation({
    mutationFn: apiClient.updateProfile,
    onSuccess: (next) => {
      queryClient.setQueryData(["profile"], next);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: apiClient.deleteAccount,
    onSuccess: async () => {
      // Right-to-erasure cleanup on the FE side: drain any in-flight events
      // queued under this identity, drop every cached query (cart + wishlist
      // live in React Query now, so this also clears them), then log out and
      // route to home.
      await clearTrackerQueue();
      queryClient.clear();
      logout();
      navigate("/", { replace: true });
    },
  });

  const deleteErrorMessage = (() => {
    if (!deleteMutation.isError) return null;
    const err = deleteMutation.error;
    if (err instanceof ApiError) {
      if (err.status === 404) return "Nothing to delete — your account already has no data on record.";
      if (err.status === 0) return "Network error. Check your connection and try again.";
      return err.message;
    }
    return "Could not delete your data. Try again in a moment.";
  })();

  const profileBusy = profileQuery.isPending || profileQuery.isLoading;
  const explanationsBusy = explanationsQuery.isPending || explanationsQuery.isLoading;

  if (profileQuery.isError) {
    return (
      <div className={`${tw.stackLg} min-h-[min(52vh,560px)] pt-8 sm:pt-10 lg:pt-12 pb-12 sm:pb-14 lg:pb-16`}>
        <p className="text-sm text-red-800/90" role="alert">
          Could not load profile lab. Check your connection and try again.
        </p>
      </div>
    );
  }

  if (!profileQuery.data) {
    return (
      <div className={`${tw.stackLg} min-h-[min(76vh,880px)] pt-8 sm:pt-10 lg:pt-12 pb-12 sm:pb-14 lg:pb-16`}>
        {profileBusy ? <ProfileLabSkeleton /> : null}
      </div>
    );
  }

  return (
    <div className={`${tw.stackLg} min-h-[min(76vh,880px)] pt-8 sm:pt-10 lg:pt-12 pb-12 sm:pb-14 lg:pb-16`}>
      <header className="max-w-3xl">
        <p className={`mb-2 text-[0.7rem] font-semibold uppercase tracking-[0.18em] ${tw.muted}`}>Profile lab</p>
        <h1 className={`${tw.storyTitle} max-w-[26ch]`}>Make the shopper model legible and editable.</h1>
        <p className={`mt-4 max-w-2xl text-pretty text-sm leading-relaxed ${tw.muted}`}>
          Explicit preferences, inferred interests, and explainability strings sit on the same canvas as catalog and
          PDP so stakeholders can narrate how signals flow. Quick actions below emit the same{" "}
          <code className="rounded bg-ink/6 px-1 py-0.5 text-[0.7rem]">profile_updated</code> events the backend plan
          expects.
        </p>
      </header>

      <ProfileSummary
        profile={profileQuery.data}
        explanations={explanationsQuery.data}
        explanationsLoading={explanationsBusy}
        explanationsError={explanationsQuery.isError}
      />

      <section className={`${tw.labPanel} ${tw.labPanelPad} max-w-xl`}>
        <p className={`text-[0.65rem] font-semibold uppercase tracking-[0.2em] ${tw.muted}`}>Demo action</p>
        <h2 className={`${tw.displayH2} mt-1 text-xl font-medium leading-snug`}>Simulate a preference shift</h2>
        <p className={`mt-2 text-sm leading-relaxed ${tw.muted}`}>
          Bumps the budget band chip so rails and search explainability can show a delta without touching the API
          contract.
        </p>
        <button
          type="button"
          className={`mt-6 ${tw.buttonEditorialBag}`}
          disabled={mutation.isPending}
          onClick={() => {
            const next = profileQuery.data.explicitPreferences.map((item) =>
              item.key === "budget" ? { ...item, value: "$40-$120" } : item,
            );
            const prevValue = profileQuery.data.explicitPreferences.find((p) => p.key === "budget")?.value;
            mutation.mutate(next);
            track({
              event_type: "profile_updated",
              payload: {
                field: "budget",
                value: "$40-$120",
                // Delta lets the worker spot magnitude of change ("$40-$120"
                // → tighter band) without re-fetching the prior profile.
                previous_value: prevValue ?? null,
                customer_segment: profileQuery.data.segment,
                top_categories: profileQuery.data.topCategories,
                inferred_interest_count: profileQuery.data.inferredInterests.length,
              },
              consent_scope: ["analytics", "personalization"],
            });
          }}
        >
          {mutation.isPending ? "Updating…" : "Simulate budget preference change"}
        </button>
        {mutation.isError ? (
          <p className="mt-3 text-sm text-red-800/90" role="alert">
            Update failed. Try again.
          </p>
        ) : null}
      </section>

      <section
        className={`${tw.labPanel} ${tw.labPanelPad} max-w-xl border-red-700/25 bg-red-50/30`}
        aria-labelledby="delete-account-heading"
      >
        <p className={`text-[0.65rem] font-semibold uppercase tracking-[0.2em] text-red-800/80`}>
          Right to erasure
        </p>
        <h2
          id="delete-account-heading"
          className={`${tw.displayH2} mt-1 text-xl font-medium leading-snug`}
        >
          Delete my data
        </h2>
        <p className={`mt-2 text-sm leading-relaxed ${tw.muted}`}>
          Wipes everything the demo has learned about you: tracked events, consent record,
          recommendation cache, and behavioral vectors. This action cannot be undone. You will be
          signed out immediately afterward.
        </p>

        {deleteArmed ? (
          <div className="mt-6 grid gap-3 rounded-card border border-red-700/30 bg-white/80 px-4 py-4 sm:px-5">
            <p className="text-sm leading-relaxed text-red-900">
              <strong className="font-semibold">Are you sure?</strong> This permanently removes your behavioral
              data from DynamoDB, OpenSearch, and Redis. Your local cart and wishlist will also be cleared.
            </p>
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                className="inline-flex min-h-10 cursor-pointer items-center justify-center rounded-pill border border-red-700/40 bg-red-700 px-5 py-2 text-[0.75rem] font-semibold text-white transition-colors hover:bg-red-800 disabled:opacity-60"
                disabled={deleteMutation.isPending}
                onClick={() => deleteMutation.mutate()}
              >
                {deleteMutation.isPending ? "Deleting…" : "Yes, delete everything"}
              </button>
              <button
                type="button"
                className={tw.buttonGhost}
                disabled={deleteMutation.isPending}
                onClick={() => setDeleteArmed(false)}
              >
                Cancel
              </button>
            </div>
            {deleteErrorMessage ? (
              <p className="text-sm text-red-800/90" role="alert">
                {deleteErrorMessage}
              </p>
            ) : null}
          </div>
        ) : (
          <button
            type="button"
            className="mt-6 inline-flex min-h-10 cursor-pointer items-center justify-center rounded-pill border border-red-700/35 bg-white/70 px-5 py-2 text-[0.75rem] font-semibold text-red-800 transition-colors hover:border-red-700/60 hover:bg-white"
            onClick={() => {
              setDeleteArmed(true);
              track({
                event_type: "delete_account_armed",
                payload: {
                  // Snapshot what's about to be wiped — useful for moderation /
                  // compliance traces and for understanding which kinds of
                  // shoppers actually pull the trigger.
                  customer_segment: profileQuery.data.segment,
                  top_categories: profileQuery.data.topCategories,
                  explicit_preference_count: profileQuery.data.explicitPreferences.length,
                  inferred_interest_count: profileQuery.data.inferredInterests.length,
                  recent_signal_count: profileQuery.data.recentSignals.length,
                  profile_last_updated: profileQuery.data.lastUpdated,
                },
                consent_scope: ["analytics", "personalization"],
              });
            }}
          >
            Delete my data…
          </button>
        )}
      </section>
    </div>
  );
}
