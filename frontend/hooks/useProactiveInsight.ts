import { useCallback, useEffect, useState } from "react";

import { buildApiUrl } from "@/services/api";
import { useAgentStore } from "@/stores/agentStore";

export type ProactiveInsight = {
  id: string;
  user_id: string;
  insight_key: string;
  category: string;
  title: string;
  content: string;
  importance: number;
  status: "pending" | "delivered" | "dismissed" | "expired";
  created_at?: string | null;
  updated_at?: string | null;
  expires_at?: string | null;
  source_memory_ids: string[];
  metadata: Record<string, unknown>;
};

export function useProactiveInsight(userId: string) {
  const memoryRefreshKey = useAgentStore((state) => state.memoryRefreshKey);
  const [insight, setInsight] = useState<ProactiveInsight | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const load = useCallback(
    async (ensureScan = false) => {
      setIsLoading(true);

      try {
        const latestResponse = await fetch(buildApiUrl(`/proactive/latest/${userId}`));
        if (!latestResponse.ok) {
          throw new Error("Could not load proactive insight.");
        }

        const latestPayload = (await latestResponse.json()) as {
          insight: ProactiveInsight | null;
        };
        if (latestPayload.insight) {
          setInsight(latestPayload.insight);
          return;
        }

        if (ensureScan) {
          const scanResponse = await fetch(buildApiUrl(`/proactive/scan/${userId}`), {
            method: "POST",
          });
          if (scanResponse.ok) {
            const scanPayload = (await scanResponse.json()) as {
              latest: ProactiveInsight | null;
            };
            setInsight(scanPayload.latest ?? null);
            return;
          }
        }

        setInsight(null);
      } catch (error) {
        setInsight(null);
      } finally {
        setIsLoading(false);
      }
    },
    [userId]
  );

  const dismiss = useCallback(async () => {
    if (!insight) {
      return;
    }

    try {
      await fetch(buildApiUrl(`/proactive/insights/${insight.id}/dismiss`), {
        method: "POST",
      });
    } finally {
      setInsight(null);
    }
  }, [insight]);

  useEffect(() => {
    void load(true);
  }, [load, memoryRefreshKey]);

  useEffect(() => {
    const interval = setInterval(() => {
      void load(false);
    }, 30000);

    return () => clearInterval(interval);
  }, [load]);

  return {
    insight,
    isLoading,
    dismiss,
    refresh: load,
  };
}
