import { useEffect, useMemo, useRef, useState } from "react";
import {
  Mic,
} from "lucide-react-native";
import {
  Animated,
  Easing,
  Platform,
  Pressable,
  SafeAreaView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { ConversationSheet } from "@/components/ConversationSheet";
import { MemoryInspector } from "@/components/MemoryInspector";
import { ModeToggle } from "@/components/ModeToggle";
import { Notification } from "@/components/Notification";
import { Orb } from "@/components/Orb";
import { useConversationFeed } from "@/hooks/useConversationFeed";
import { useAgent } from "@/hooks/useAgent";
import { useProactiveInsight } from "@/hooks/useProactiveInsight";

const PREVIEW_INSIGHT = {
  title: "There’s a pattern worth naming",
  content:
    "You seem to get the most momentum when the next step is small enough to do immediately. I’d make today’s move concrete, visible, and almost too easy to avoid.",
};

export default function HomeScreen() {
  const isWeb = Platform.OS === "web";
  const [atlasOpen, setAtlasOpen] = useState(false);
  const [chatModeOpen, setChatModeOpen] = useState(false);
  const [orbModeProgress, setOrbModeProgress] = useState(0);
  const [composerDraft, setComposerDraft] = useState("");
  const [isSendingText, setIsSendingText] = useState(false);
  const [pendingUserText, setPendingUserText] = useState<string | null>(null);
  const [previewInsightDismissed, setPreviewInsightDismissed] = useState(false);
  const [insightAnimationActive, setInsightAnimationActive] = useState(false);
  const modeProgress = useRef(new Animated.Value(0)).current;
  const insightReveal = useRef(new Animated.Value(0)).current;
  const {
    isListening,
    isSpeaking,
    isThinking,
    responsePreview,
    statusMessage,
    sendTextMessage,
    startListening,
    stopListening,
  } = useAgent();
  const { insight, dismiss } = useProactiveInsight("local-user");
  const { turns, isLoading: isConversationLoading, error: conversationError } =
    useConversationFeed("local-user", chatModeOpen);
  const previewInsightEnabled = useMemo(() => {
    if (!isWeb || typeof window === "undefined") {
      return false;
    }

    return new URLSearchParams(window.location.search).get("previewInsight") === "1";
  }, [isWeb]);
  const displayInsight =
    insight ?? (previewInsightEnabled && !previewInsightDismissed ? PREVIEW_INSIGHT : null);
  const displayInsightKey = displayInsight
    ? `${displayInsight.title}:${displayInsight.content}`
    : "";
  const dismissDisplayInsight = insight ? dismiss : () => setPreviewInsightDismissed(true);

  useEffect(() => {
    if (!pendingUserText) {
      return;
    }

    const matched = turns.some(
      (turn) => turn.role === "user" && turn.text.trim() === pendingUserText.trim()
    );
    if (matched) {
      setPendingUserText(null);
    }
  }, [pendingUserText, turns]);

  useEffect(() => {
    Animated.timing(modeProgress, {
      toValue: chatModeOpen ? 1 : 0,
      duration: chatModeOpen ? 720 : 620,
      easing: Easing.inOut(Easing.cubic),
      useNativeDriver: false,
    }).start();
  }, [chatModeOpen, modeProgress]);

  useEffect(() => {
    const listenerId = modeProgress.addListener(({ value }) => {
      setOrbModeProgress(value);
    });

    return () => {
      modeProgress.removeListener(listenerId);
    };
  }, [modeProgress]);

  useEffect(() => {
    if (!displayInsight) {
      setInsightAnimationActive(false);
      return;
    }

    setInsightAnimationActive(false);
    insightReveal.setValue(0);
    const timeout = setTimeout(() => {
      setInsightAnimationActive(true);
      Animated.timing(insightReveal, {
        toValue: 1,
        duration: 1050,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: true,
      }).start();
    }, 900);

    return () => clearTimeout(timeout);
  }, [displayInsight, displayInsightKey, insightReveal]);

  const handleSendText = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isSendingText) {
      return false;
    }

    setIsSendingText(true);
    const didSend = await sendTextMessage(trimmed);
    if (didSend) {
      setPendingUserText(trimmed);
      setComposerDraft("");
    }
    setIsSendingText(false);
    return didSend;
  };

  const shellStyles = useMemo(
    () => [
      styles.container,
      isWeb && atlasOpen ? styles.containerWithAtlas : null,
    ],
    [atlasOpen, isWeb]
  );

  const experienceStyles = useMemo(
    () => [
      styles.experiencePanel,
      isWeb && atlasOpen ? styles.experiencePanelCompressed : null,
      chatModeOpen ? styles.experiencePanelChatMode : null,
    ],
    [atlasOpen, chatModeOpen, isWeb]
  );

  const heroHeight = modeProgress.interpolate({
    inputRange: [0, 1],
    outputRange: [520, 128],
  });

  const orbScale = modeProgress.interpolate({
    inputRange: [0, 0.52, 1],
    outputRange: [1, 0.98, 1],
  });

  const orbLift = modeProgress.interpolate({
    inputRange: [0, 1],
    outputRange: [96, -49],
  });

  const captionOpacity = modeProgress.interpolate({
    inputRange: [0, 1],
    outputRange: [1, 0],
  });

  const captionLift = modeProgress.interpolate({
    inputRange: [0, 1],
    outputRange: [0, -18],
  });

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={shellStyles}>
        <View style={experienceStyles}>
          <View style={styles.topBar}>
            <View />

            {isWeb ? (
              <Pressable
                onPress={() => setAtlasOpen((current) => !current)}
                style={styles.atlasToggle}
              >
                <Text style={styles.atlasToggleLabel}>
                  {atlasOpen ? "Hide Atlas" : "Open Atlas"}
                </Text>
              </Pressable>
            ) : null}
          </View>

          <Animated.View style={[styles.centerpiece, { height: heroHeight }]}>
            <Animated.View
              style={[
                styles.orbModeShell,
                {
                  transform: [{ translateY: orbLift }, { scale: orbScale }],
                },
              ]}
            >
              {displayInsight ? (
                <Animated.View
                  style={[
                    styles.orbInsightDock,
                    {
                      opacity: Animated.multiply(captionOpacity, insightReveal),
                      transform: [
                        { translateY: -58 },
                        {
                          scale: insightReveal.interpolate({
                            inputRange: [0, 1],
                            outputRange: [0.72, 0.88],
                          }),
                        },
                      ],
                    },
                  ]}
                >
                  <Notification
                    title={displayInsight.title}
                    text={displayInsight.content}
                    onDismiss={dismissDisplayInsight}
                  />
                </Animated.View>
              ) : null}
              <Orb
                isListening={isListening}
                isSpeaking={isSpeaking}
                isThinking={isThinking}
                modeProgress={orbModeProgress}
                insightOpen={insightAnimationActive}
              />
            </Animated.View>
            <Animated.View
              style={[
                styles.captionStack,
                {
                  opacity: captionOpacity,
                  transform: [{ translateY: captionLift }],
                },
              ]}
            >
              {responsePreview && !isListening ? (
                <Text style={styles.responsePreview} numberOfLines={4}>
                  {responsePreview}
                </Text>
              ) : null}
            </Animated.View>
          </Animated.View>

          <ConversationSheet
            visible={chatModeOpen}
            progress={modeProgress}
            turns={turns}
            pendingUserText={pendingUserText}
            responsePreview={responsePreview}
            draft={composerDraft}
            isThinking={isThinking}
            isSpeaking={isSpeaking}
            isListening={isListening}
            isLoading={isConversationLoading}
            isSending={isSendingText}
            error={conversationError}
            onDraftChange={setComposerDraft}
            onSend={handleSendText}
          />

          <Animated.View
            style={[
              styles.footer,
              {
              },
            ]}
          >
            <View style={styles.actionStack}>
              {!chatModeOpen ? (
                <Animated.View
                  style={[
                    styles.speakButtonWrap,
                    {
                      opacity: modeProgress.interpolate({
                        inputRange: [0, 0.55, 1],
                        outputRange: [1, 0.12, 0],
                      }),
                      transform: [
                        {
                          translateY: modeProgress.interpolate({
                            inputRange: [0, 1],
                            outputRange: [0, 14],
                          }),
                        },
                      ],
                    },
                  ]}
                >
                  <Pressable
                    accessibilityLabel="Hold to speak"
                    onPressIn={startListening}
                    onPressOut={stopListening}
                    style={({ pressed }) => [
                      styles.speakButton,
                      pressed ? styles.speakButtonPressed : null,
                      isListening ? styles.speakButtonListening : null,
                    ]}
                  >
                    <Mic size={23} color="#EAF4FF" strokeWidth={2.2} />
                  </Pressable>
                </Animated.View>
              ) : (
                <View style={styles.speakButtonSpacer} />
              )}
              <ModeToggle
                mode={chatModeOpen ? "chat" : "voice"}
                onChange={(mode) => setChatModeOpen(mode === "chat")}
              />
            </View>
          </Animated.View>
        </View>

        {isWeb ? (
          <MemoryInspector
            userId="local-user"
            visible={atlasOpen}
            onClose={() => setAtlasOpen(false)}
          />
        ) : null}

      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: "#080B14",
  },
  container: {
    flex: 1,
    backgroundColor: "#080B14",
  },
  containerWithAtlas: {
    flexDirection: "row",
  },
  experiencePanel: {
    flex: 1,
    justifyContent: "space-between",
    paddingHorizontal: 24,
    paddingTop: 20,
    paddingBottom: 44,
    backgroundColor: "#080B14",
    position: "relative",
  },
  experiencePanelCompressed: {
    minWidth: 0,
    paddingHorizontal: 32,
    paddingRight: 20,
  },
  experiencePanelChatMode: {
    justifyContent: "flex-start",
    gap: 6,
    paddingBottom: 16,
  },
  topBar: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 16,
    minHeight: 40,
  },
  atlasToggle: {
    minHeight: 40,
    paddingHorizontal: 16,
    borderRadius: 999,
    backgroundColor: "#111A2B",
    borderWidth: 1,
    borderColor: "rgba(146,229,255,0.22)",
    justifyContent: "center",
  },
  atlasToggleLabel: {
    color: "#EFF5FF",
    fontSize: 13,
    fontWeight: "700",
    letterSpacing: 0.8,
  },
  centerpiece: {
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
    width: "100%",
    alignSelf: "center",
    position: "relative",
    zIndex: 20,
  },
  orbModeShell: {
    alignItems: "center",
    justifyContent: "center",
    width: "100%",
    marginTop: 0,
    position: "relative",
    zIndex: 21,
  },
  orbInsightDock: {
    position: "absolute",
    top: "50%",
    left: 24,
    right: 24,
    alignItems: "center",
    zIndex: 24,
  },
  captionStack: {
    alignItems: "center",
    gap: 8,
    marginTop: -18,
    maxWidth: 540,
  },
  caption: {
    color: "#DCE6F9",
    fontSize: 18,
    fontWeight: "600",
    textAlign: "center",
    lineHeight: 24,
  },
  captionHint: {
    color: "#8698BE",
    fontSize: 13,
    lineHeight: 18,
    textAlign: "center",
  },
  responsePreview: {
    maxWidth: 420,
    color: "#C7D5F3",
    fontSize: 15,
    lineHeight: 22,
    textAlign: "center",
  },
  footer: {
    position: "absolute",
    left: 24,
    right: 24,
    bottom: 20,
    gap: 14,
    alignItems: "center",
    zIndex: 30,
  },
  actionStack: {
    width: "100%",
    maxWidth: 300,
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
  },
  speakButtonWrap: {
    height: 52,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 26,
  },
  speakButtonSpacer: {
    height: 78,
  },
  speakButton: {
    width: 52,
    height: 52,
    borderRadius: 999,
    backgroundColor: "#0D1321",
    borderWidth: 1,
    borderColor: "rgba(146, 229, 255, 0.2)",
    justifyContent: "center",
    alignItems: "center",
    shadowColor: "#84ECFF",
    shadowOpacity: 0.16,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 0 },
  },
  speakButtonPressed: {
    transform: [{ scale: 0.97 }],
    opacity: 0.92,
  },
  speakButtonListening: {
    borderColor: "rgba(132, 236, 255, 0.62)",
    backgroundColor: "rgba(37, 72, 108, 0.72)",
  },
});
