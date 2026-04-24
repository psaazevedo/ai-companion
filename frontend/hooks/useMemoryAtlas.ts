import { useCallback, useEffect, useState } from "react";

import { buildApiUrl } from "@/services/api";
import { useAgentStore } from "@/stores/agentStore";

export type AtlasNode = {
  id: string;
  label: string;
  layer: "core" | "semantic" | "procedural";
  group: string;
  status: "active" | "archived" | "pinned";
  content: string;
  strength: number;
  confidence: number;
  reinforcement_count: number;
  recall_count: number;
  updated_at: string | null;
  archive_reason?: string | null;
};

export type AtlasEdge = {
  id: string;
  source: string;
  target: string;
  weight: number;
  relation: string;
};

export type AtlasRelation = {
  id: string;
  source_label: string;
  target_label: string;
  relation: string;
  weight: number;
  recall_count: number;
  last_seen: string | null;
};

export type AtlasTimelineEntry = {
  id: string;
  timestamp: string | null;
  title: string;
  summary: string;
  emotional_tone: string;
  salience: number;
  recall_count: number;
  memory_status: "active" | "archived" | "pinned";
};

export type MemoryAtlasSnapshot = {
  user_id: string;
  generated_at: string;
  summary: {
    episodes: number;
    semantic: number;
    procedural: number;
    graph_nodes: number;
    graph_edges: number;
    status_counts: Record<string, number>;
  };
  map: {
    nodes: AtlasNode[];
    edges: AtlasEdge[];
    relations: AtlasRelation[];
  };
  timeline: AtlasTimelineEntry[];
  evidence: Record<string, AtlasTimelineEntry[]>;
};

export function useMemoryAtlas(userId: string, enabled = true) {
  const memoryRefreshKey = useAgentStore((state) => state.memoryRefreshKey);
  const [snapshot, setSnapshot] = useState<MemoryAtlasSnapshot | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!enabled) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(buildApiUrl(`/memory/atlas/${userId}`));
      if (!response.ok) {
        throw new Error(`Atlas request failed (${response.status})`);
      }
      const data = (await response.json()) as MemoryAtlasSnapshot;
      setSnapshot(data);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Could not load the memory atlas."
      );
    } finally {
      setIsLoading(false);
    }
  }, [enabled, userId]);

  useEffect(() => {
    void load();
  }, [load, memoryRefreshKey]);

  return {
    snapshot,
    isLoading,
    error,
    refresh: load,
  };
}
