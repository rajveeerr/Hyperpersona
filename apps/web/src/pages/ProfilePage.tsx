import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ProfileLabSkeleton } from "@/features/profile/components/ProfileLabSkeleton";
import { ProfileSummary } from "@/features/profile/components/ProfileSummary";
import { useTrackEvent } from "@/features/events/useTrackEvent";
import { apiClient } from "@/shared/api/client";
import { tw } from "@/shared/ui/tw";

export function ProfilePage() {
  const queryClient = useQueryClient();
  const track = useTrackEvent();
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
            mutation.mutate(next);
            track({
              customer_id: "demo-customer-1",
              event_type: "profile_updated",
              payload: { field: "budget", value: "$40-$120" },
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
    </div>
  );
}
