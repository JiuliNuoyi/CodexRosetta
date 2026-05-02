import { useState, useEffect, useCallback } from "react";

export interface SettingsData {
  LOG_LEVEL: string;
  LOG_UPSTREAM_REQUESTS: boolean;
  LOG_UPSTREAM_RESPONSES: boolean;
  DEBUG_LOG_FILE: string | null;
  WEB_SEARCH_ENABLED: boolean;
  WEB_SEARCH_PROVIDER: string;
  WEB_SEARCH_BASE_URL: string;
  WEB_SEARCH_API_KEY: string;
  WEB_SEARCH_MAX_RESULTS: number;
  WEB_SEARCH_MAX_ROUNDS: number;
}

export function useSettings() {
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSettings = useCallback(async () => {
    try {
      const res = await fetch("/v1/settings");
      if (!res.ok) throw new Error("Failed to fetch settings");
      const data = await res.json();
      setSettings({
        LOG_LEVEL: data.settings.LOG_LEVEL,
        LOG_UPSTREAM_REQUESTS: data.settings.LOG_UPSTREAM_REQUESTS,
        LOG_UPSTREAM_RESPONSES: data.settings.LOG_UPSTREAM_RESPONSES,
        DEBUG_LOG_FILE: data.settings.DEBUG_LOG_FILE,
        WEB_SEARCH_ENABLED: data.settings.WEB_SEARCH_ENABLED,
        WEB_SEARCH_PROVIDER: data.settings.WEB_SEARCH_PROVIDER,
        WEB_SEARCH_BASE_URL: data.settings.WEB_SEARCH_BASE_URL,
        WEB_SEARCH_API_KEY: data.settings.WEB_SEARCH_API_KEY,
        WEB_SEARCH_MAX_RESULTS: data.settings.WEB_SEARCH_MAX_RESULTS,
        WEB_SEARCH_MAX_ROUNDS: data.settings.WEB_SEARCH_MAX_ROUNDS,
      });
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const updateSettings = useCallback(
    async (updates: Partial<SettingsData>) => {
      setSaving(true);
      setError(null);
      try {
        const res = await fetch("/v1/settings", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(updates),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || "Failed to update settings");
        }
        const data = await res.json();
        setSettings({
          LOG_LEVEL: data.settings.LOG_LEVEL,
          LOG_UPSTREAM_REQUESTS: data.settings.LOG_UPSTREAM_REQUESTS,
          LOG_UPSTREAM_RESPONSES: data.settings.LOG_UPSTREAM_RESPONSES,
          DEBUG_LOG_FILE: data.settings.DEBUG_LOG_FILE,
          WEB_SEARCH_ENABLED: data.settings.WEB_SEARCH_ENABLED,
          WEB_SEARCH_PROVIDER: data.settings.WEB_SEARCH_PROVIDER,
          WEB_SEARCH_BASE_URL: data.settings.WEB_SEARCH_BASE_URL,
          WEB_SEARCH_API_KEY: data.settings.WEB_SEARCH_API_KEY,
          WEB_SEARCH_MAX_RESULTS: data.settings.WEB_SEARCH_MAX_RESULTS,
          WEB_SEARCH_MAX_ROUNDS: data.settings.WEB_SEARCH_MAX_ROUNDS,
        });
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Unknown error");
        throw e;
      } finally {
        setSaving(false);
      }
    },
    []
  );

  return { settings, loading, saving, error, updateSettings, refresh: fetchSettings };
}
