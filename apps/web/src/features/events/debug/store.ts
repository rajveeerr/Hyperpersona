import { create } from "zustand/react";

import type { TrackedEvent } from "@/shared/api/contracts";

type DebugEventStore = {
  events: TrackedEvent[];
  push: (event: TrackedEvent) => void;
};

export const useDebugEventStore = create<DebugEventStore>((set) => ({
  events: [],
  push: (event) =>
    set((state) => ({
      events: [event, ...state.events].slice(0, 20),
    })),
}));
