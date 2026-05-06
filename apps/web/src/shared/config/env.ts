const envSchema = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? "/api",
  debugPanelEnabled: import.meta.env.VITE_ENABLE_DEBUG_PANEL !== "false",
} as const;

export const env = envSchema;
