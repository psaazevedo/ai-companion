import { create } from "zustand";

export type ConversationState =
  | "connecting"
  | "ready"
  | "listening"
  | "thinking"
  | "speaking"
  | "interrupting"
  | "reconnecting"
  | "error";

type AgentStore = {
  conversationState: ConversationState;
  isConnected: boolean;
  isListening: boolean;
  isSpeaking: boolean;
  isThinking: boolean;
  orbInputLevel: number;
  statusMessage: string;
  memoryRefreshKey: number;
  setConversationState: (value: ConversationState) => void;
  setConnected: (value: boolean) => void;
  setListening: (value: boolean) => void;
  setSpeaking: (value: boolean) => void;
  setThinking: (value: boolean) => void;
  setOrbInputLevel: (value: number) => void;
  setStatusMessage: (value: string) => void;
  bumpMemoryRefreshKey: () => void;
};

export const useAgentStore = create<AgentStore>((set) => ({
  conversationState: "connecting",
  isConnected: false,
  isListening: false,
  isSpeaking: false,
  isThinking: false,
  orbInputLevel: 0,
  statusMessage: "Connecting...",
  memoryRefreshKey: 0,
  setConversationState: (value) => set({ conversationState: value }),
  setConnected: (value) => set({ isConnected: value }),
  setListening: (value) => set({ isListening: value }),
  setSpeaking: (value) => set({ isSpeaking: value }),
  setThinking: (value) => set({ isThinking: value }),
  setOrbInputLevel: (value) => set({ orbInputLevel: value }),
  setStatusMessage: (value) => set({ statusMessage: value }),
  bumpMemoryRefreshKey: () =>
    set((state) => ({ memoryRefreshKey: state.memoryRefreshKey + 1 })),
}));
