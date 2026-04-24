import { useCallback, useEffect, useState } from "react";

import { buildApiUrl } from "@/services/api";
import { useAgentStore } from "@/stores/agentStore";

export type ConversationTurn = {
  id: string;
  episode_id: string;
  role: "user" | "assistant";
  input_mode: "voice" | "text";
  text: string;
  timestamp: string | null;
  emotional_tone: string;
  salience: number;
  memory_status: "active" | "archived" | "pinned";
  summary: string;
};

type ConversationFeed = {
  user_id: string;
  generated_at: string;
  episodes: number;
  turns: ConversationTurn[];
};

export function useConversationFeed(userId: string, enabled = true) {
  const memoryRefreshKey = useAgentStore((state) => state.memoryRefreshKey);
  const [feed, setFeed] = useState<ConversationFeed | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!enabled) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(buildApiUrl(`/memory/conversation/${userId}?limit=60`));
      if (!response.ok) {
        throw new Error(`Conversation request failed (${response.status})`);
      }
      const data = (await response.json()) as ConversationFeed;
      setFeed(data);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Could not load the conversation feed."
      );
    } finally {
      setIsLoading(false);
    }
  }, [enabled, userId]);

  useEffect(() => {
    void load();
  }, [load, memoryRefreshKey]);

  return {
    feed,
    turns: feed?.turns ?? [],
    isLoading,
    error,
    refresh: load,
  };
}
