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

const LONG_THREAD_BASE_TIME = Date.now();

function simulatedTimestamp(minutesAgo: number) {
  return new Date(LONG_THREAD_BASE_TIME - minutesAgo * 60_000).toISOString();
}

function simulatedTurn(
  id: string,
  episodeId: string,
  role: "user" | "assistant",
  text: string,
  minutesAgo: number,
  emotionalTone = "focused"
): ConversationTurn {
  return {
    id,
    episode_id: episodeId,
    role,
    input_mode: "text",
    text,
    timestamp: simulatedTimestamp(minutesAgo),
    emotional_tone: emotionalTone,
    salience: role === "user" ? 0.82 : 0.88,
    memory_status: "active",
    summary: "Long thread simulation for chat lens stress testing.",
  };
}

const LONG_THREAD_TURNS: ConversationTurn[] = [
  simulatedTurn(
    "long-user-1",
    "long-simulation-1",
    "user",
    "I want to stress test the conversation lens with a very long prompt. Imagine I am explaining a complicated situation with a lot of context: I am building a personal AI companion, I care deeply about memory architecture, I want the interface to feel calm and alive, and I keep noticing that most assistants feel brittle because they do not carry the emotional and historical continuity of a real relationship. I am also trying to decide whether the system should prioritize memory consolidation, live speech interruption, proactive insights, or the visual language of the orb next. Please respond as if this were a real, detailed product strategy question rather than a quick chat message.",
    18
  ),
  simulatedTurn(
    "long-assistant-1",
    "long-simulation-1",
    "assistant",
    "For this stage, I would treat the product as having two fragile promises: it must feel present in the moment, and it must compound over time. The memory architecture is the moat, but the conversational surface is how the user learns to trust the moat. If the speech interaction feels mechanical or interrupt-heavy, the memory system may be technically strong but emotionally invisible. If the interface feels beautiful but the memory is shallow, the product becomes an impressive shell. So I would sequence the work in layers. First, stabilize the conversation loop: voice, text, interruption handling, streaming, and clear state. Second, make memory retrieval explainable enough that the companion can naturally say why it remembers something and how confident it is. Third, improve consolidation so repeated ideas reinforce existing beliefs instead of creating duplicates. Fourth, introduce proactive insights only when they are genuinely specific and useful. The orb and chat lens matter because they make the relationship feel embodied, but they should support the underlying intelligence rather than distract from it. In practical terms, I would not choose between memory and conversation. I would build the next slice where they meet: a companion that listens fluidly, remembers what matters, and can show the evidence behind its understanding when asked.",
    17,
    "grounded"
  ),
  simulatedTurn(
    "long-user-2",
    "long-simulation-2",
    "user",
    "Now make the test harder. Suppose I ramble for a while because that is how I actually think out loud. I might say: I know we need memory, but memory is not just storing messages, right? It is episodic recall, semantic abstraction, procedures for helping me, graph relationships, private scopes, confidence, contradiction handling, and lifecycle. I also keep changing my mind about the interface because the product needs to feel like a companion, not a dashboard. I worry that if we add too many panels, it becomes enterprise software, but if we hide too much, I cannot trust what it knows. I also want the model to access the internet, weather, news, finance, and other context, but without becoming noisy or overconfident. So the real question is: how do we design a system that can take this messy, multi-part thought, answer the actual underlying question, and remember the useful parts without creating five duplicate memories that all say the same thing in different words?",
    12,
    "rambling"
  ),
  simulatedTurn(
    "long-assistant-2",
    "long-simulation-2",
    "assistant",
    "The underlying question is not really about one feature. It is about whether the companion can transform messy human input into durable understanding without flattening the human. I would split that into three responsibilities. First, the conversation layer should tolerate imperfect speech: rambling, repetition, correction, hesitation, and half-formed thoughts should be treated as signal, not noise. The model should summarize the point after listening, but it should not punish the user for thinking in public. Second, the memory layer should separate evidence from belief. The raw episode remains intact as proof of what happened. Semantic memory should only be created when the system can name a stable belief or preference with enough confidence. Similar memories should reinforce the same belief rather than create duplicates. If a private context reinforces a belief that is already global, it can increase confidence only inside that private scope unless the user explicitly allows it to generalize. Third, the interface should expose this without becoming heavy. The main surface should remain calm: voice, chat, and the orb. The Atlas should be the place where the system explains why it believes something, what episodes support it, whether the belief is global or scoped, and what can be corrected. That gives you the best of both worlds: the companion feels natural in the moment, but the architecture remains inspectable when trust matters.",
    11,
    "grounded"
  ),
  simulatedTurn(
    "long-user-3",
    "long-simulation-3",
    "user",
    "Give me the extreme case: I ask one very short thing, but the answer is huge.",
    7
  ),
  simulatedTurn(
    "long-assistant-3",
    "long-simulation-3",
    "assistant",
    "A short question can still deserve a long answer, so the UI should not assume that message length on one side predicts message length on the other. In the conversation lens, this means the exchange should be measured as a combined unit: prompt, connector, answer, and breathing room. If the answer becomes long, the active exchange should grow vertically and remain the dominant focus while the user scrolls through it. Older and newer exchanges should recede, but the current answer should not shrink before the user has had a chance to finish reading it. The key is that focus should be tied to the scroll position inside the exchange, not just to the center point of a fixed-size card. Practically, that means we estimate or measure the height of each exchange, give long answers more vertical territory, and keep the active scale at full strength across the middle band of that territory. Only when the user moves beyond the answer should the next exchange begin to take over.\n\nThere is also an interaction nuance: if an answer is very long, the composer still needs to stay reachable, but it should not visually compete with the reading area. The current bottom composer works for this because it stays fixed and predictable. On mobile, the exchange width should tighten less aggressively so text does not become a narrow newspaper column. On desktop, the exchange can remain centered and moderate in width because huge full-width text is harder to read. The orb should stay as a presence marker, but not sit on top of the message or look like another message object. This is why the long-message test matters: it reveals whether the lens is truly a reading surface or only a pretty animation for short snippets.\n\nFor memory, long answers also create a different risk. The system should not store the whole answer as a new belief. It should store the episode, then extract only durable claims: for example, that the user cares about focus continuity, that long messages must not clip, and that mobile spacing needs to preserve readability. The raw episode remains recoverable, but semantic memory should be concise and reinforced only when repeated.",
    6,
    "grounded"
  ),
  simulatedTurn(
    "long-user-4",
    "long-simulation-4",
    "user",
    "One more: imagine I paste a long product note with several priorities. I want the chat to handle this kind of input without cropping it. The note says the companion should feel like a human-like friend, but not fake intimacy. It should remember my speech patterns, including if I stutter, ramble, or circle around an idea before naming it. It should know when to interrupt and when to wait. It should use tools for weather and internet only when the question actually needs current information. It should treat proactive insights as rare and high-value, not a stream of generic coaching. It should support different agent modes eventually, but with shared memory and scoped privacy so a secret told to one mode is not automatically exposed to another. And the UI should make all of this feel simple: one presence, one relationship, enough transparency to trust it.",
    3,
    "focused"
  ),
  simulatedTurn(
    "long-assistant-4",
    "long-simulation-4",
    "assistant",
    "That note should become one readable exchange, not a clipped pill. The companion should answer the product-level priority: build the relationship loop first, then deepen memory, then add scoped modes and tools. The UI test is whether this whole thought can stay visible long enough to be understood.",
    2,
    "grounded"
  ),
];

export function useConversationFeed(userId: string, enabled = true) {
  const memoryRefreshKey = useAgentStore((state) => state.memoryRefreshKey);
  const [feed, setFeed] = useState<ConversationFeed | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!enabled) {
      return;
    }

    if (shouldSimulateLongThread()) {
      setFeed({
        user_id: userId,
        generated_at: new Date().toISOString(),
        episodes: 4,
        turns: LONG_THREAD_TURNS,
      });
      setIsLoading(false);
      setError(null);
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

function shouldSimulateLongThread() {
  if (typeof window === "undefined") {
    return false;
  }

  return new URLSearchParams(window.location.search).get("simulateLongThread") === "1";
}
