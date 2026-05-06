import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useState } from "react";
import { RouterProvider } from "react-router-dom";

import type { router } from "@/app/router";

type AppProvidersProps = {
  router: typeof router;
};

function createClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
      },
      mutations: {
        retry: 0,
      },
    },
  });
}

export function AppProviders({ router }: AppProvidersProps) {
  const [queryClient] = useState(createClient);

  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}

export function AppProviderBoundary({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
