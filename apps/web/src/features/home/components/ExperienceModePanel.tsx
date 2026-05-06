import type { ConsentRecord, ProfileSummary } from "@/shared/api/contracts";
import { tw } from "@/shared/ui/tw";

type ExperienceModePanelProps = {
  consent: ConsentRecord;
  profile: ProfileSummary;
};

export const ExperienceModePanel = ({ consent, profile }: ExperienceModePanelProps) => {
  const personalized = consent.scopes.includes("personalization");

  return (
    <section
      className={`${tw.surface} ${tw.surfacePad} grid grid-cols-[1.1fr_0.9fr] gap-6 max-[960px]:grid-cols-1`}
    >
      <div className={tw.stackMd}>
        <span className={tw.eyebrow}>Experience mode</span>
        <h2 className={`${tw.displayH2} text-3xl`}>{personalized ? "Personalized Mode Is Active" : "Generic Mode Is Active"}</h2>
        <p className={tw.muted}>
          {personalized
            ? `The app is currently using ${profile.segment.toLowerCase()} signals, consented activity, and recent behavior to shape ranking and recommendation surfaces.`
            : "The app is intentionally using generic merchandising behavior because personalization consent is not active."}
        </p>
      </div>
      <div className="grid content-center gap-4">
        <div>
          <strong>{personalized ? "Consent enabled" : "Consent disabled"}</strong>
          <p className={tw.muted}>This should visibly change recommendation confidence and search behavior.</p>
        </div>
        <div>
          <strong>{profile.topCategories.join(" · ")}</strong>
          <p className={tw.muted}>These are the dominant categories currently shaping the shopper profile.</p>
        </div>
      </div>
    </section>
  );
};
