import { useState, useEffect, useCallback } from "react";

export interface KeyEntry {
  name: string;
  key_masked: string;
  provider: string;
  base_url: string;
  models: string[];
  active: boolean;
}

export function useKeys() {
  const [keys, setKeys] = useState<KeyEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchKeys = useCallback(async () => {
    try {
      const res = await fetch("/v1/keys");
      if (!res.ok) throw new Error("Failed to fetch keys");
      const data = await res.json();
      setKeys(data);
      setError(null);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchKeys();
  }, [fetchKeys]);

  const addKey = useCallback(
    async (input: {
      name: string;
      key: string;
      provider: string;
      base_url: string;
      models: string[];
      active?: boolean;
    }) => {
      const res = await fetch("/v1/keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to add key");
      }
      await fetchKeys();
    },
    [fetchKeys]
  );

  const deleteKey = useCallback(
    async (name: string) => {
      const res = await fetch(`/v1/keys/${encodeURIComponent(name)}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("Failed to delete key");
      await fetchKeys();
    },
    [fetchKeys]
  );

  const activateKey = useCallback(
    async (name: string) => {
      const res = await fetch(
        `/v1/keys/${encodeURIComponent(name)}/activate`,
        { method: "PUT" }
      );
      if (!res.ok) throw new Error("Failed to activate key");
      await fetchKeys();
    },
    [fetchKeys]
  );

  const updateKey = useCallback(
    async (
      name: string,
      fields: {
        key?: string;
        provider?: string;
        base_url?: string;
        models?: string[];
        active?: boolean;
      }
    ) => {
      const res = await fetch(`/v1/keys/${encodeURIComponent(name)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(fields),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to update key");
      }
      await fetchKeys();
    },
    [fetchKeys]
  );

  return { keys, loading, error, addKey, updateKey, deleteKey, activateKey, refresh: fetchKeys };
}
