import { create } from "zustand/react";

import { defaultPersona, demoPersonas } from "@/features/personas/data";

type PersonaStore = {
  currentPersonaId: string;
  setPersona: (personaId: string) => void;
};

function runPersonaUpdate(personaId: string, set: (partial: Partial<PersonaStore>) => void) {
  if (!demoPersonas.some((persona) => persona.id === personaId)) {
    return;
  }
  set({ currentPersonaId: personaId });
}

export const usePersonaStore = create<PersonaStore>((set) => ({
  currentPersonaId: defaultPersona.id,
  setPersona: (personaId) => {
    const doc = document as Document & { startViewTransition?: (cb: () => void) => unknown };
    const apply = () => runPersonaUpdate(personaId, set);
    if (typeof doc.startViewTransition === "function") {
      doc.startViewTransition(apply);
    } else {
      apply();
    }
  },
}));

export const useCurrentPersona = () => {
  const currentPersonaId = usePersonaStore((state) => state.currentPersonaId);
  return demoPersonas.find((persona) => persona.id === currentPersonaId) ?? defaultPersona;
};
