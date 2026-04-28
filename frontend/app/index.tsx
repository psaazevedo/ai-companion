import { useEffect, useMemo, useRef, useState } from "react";
import {
  Mic,
  UserRound,
  X,
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
  const atlasProgress = useRef(new Animated.Value(0)).current;
  const insightReveal = useRef(new Animated.Value(0)).current;
  const listeningPulse = useRef(new Animated.Value(0)).current;
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
    if (!isWeb || typeof document === "undefined") {
      return;
    }

    const html = document.documentElement;
    const body = document.body;
    const appRoot =
      document.getElementById("root") ??
      document.getElementById("__next") ??
      (body.firstElementChild instanceof HTMLElement ? body.firstElementChild : null);
    const previousHtmlHeight = html.style.height;
    const previousHtmlOverflow = html.style.overflow;
    const previousHtmlBackground = html.style.backgroundColor;
    const previousBodyHeight = body.style.height;
    const previousBodyOverflow = body.style.overflow;
    const previousBodyWidth = body.style.width;
    const previousBodyOverscroll = body.style.overscrollBehavior;
    const previousBodyBackground = body.style.backgroundColor;
    const previousRootHeight = appRoot?.style.height ?? "";
    const previousRootMaxHeight = appRoot?.style.maxHeight ?? "";
    const previousRootOverflow = appRoot?.style.overflow ?? "";

    html.style.height = "100%";
    html.style.overflow = "hidden";
    html.style.backgroundColor = "#080B14";
    body.style.height = "100vh";
    body.style.overflow = "hidden";
    body.style.width = "100%";
    body.style.overscrollBehavior = "none";
    body.style.backgroundColor = "#080B14";
    if (appRoot) {
      appRoot.style.height = "100vh";
      appRoot.style.maxHeight = "100vh";
      appRoot.style.overflow = "hidden";
      appRoot.scrollTop = 0;
    }

    return () => {
      html.style.height = previousHtmlHeight;
      html.style.overflow = previousHtmlOverflow;
      html.style.backgroundColor = previousHtmlBackground;
      body.style.height = previousBodyHeight;
      body.style.overflow = previousBodyOverflow;
      body.style.width = previousBodyWidth;
      body.style.overscrollBehavior = previousBodyOverscroll;
      body.style.backgroundColor = previousBodyBackground;
      if (appRoot) {
        appRoot.style.height = previousRootHeight;
        appRoot.style.maxHeight = previousRootMaxHeight;
        appRoot.style.overflow = previousRootOverflow;
      }
    };
  }, [isWeb]);

  useEffect(() => {
    if (!isWeb || typeof window === "undefined") {
      return;
    }

    const keepAppCanvasPinned = () => {
      window.scrollTo({ top: 0, left: 0, behavior: "auto" });
      document.scrollingElement?.scrollTo?.(0, 0);
      document.documentElement.scrollTop = 0;
      document.body.scrollTop = 0;
      const appRoot =
        document.getElementById("root") ??
        document.getElementById("__next") ??
        (document.body.firstElementChild instanceof HTMLElement
          ? document.body.firstElementChild
          : null);
      if (appRoot) {
        appRoot.scrollTop = 0;
      }
    };

    keepAppCanvasPinned();
    window.requestAnimationFrame(keepAppCanvasPinned);
    const timeouts = [80, 180, 360, 720].map((delay) =>
      setTimeout(keepAppCanvasPinned, delay)
    );

    return () => {
      timeouts.forEach(clearTimeout);
    };
  }, [chatModeOpen, isWeb]);

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
    Animated.timing(atlasProgress, {
      toValue: atlasOpen ? 1 : 0,
      duration: atlasOpen ? 520 : 420,
      easing: Easing.inOut(Easing.cubic),
      useNativeDriver: true,
    }).start();
  }, [atlasOpen, atlasProgress]);

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

  useEffect(() => {
    if (!isListening) {
      listeningPulse.stopAnimation();
      Animated.timing(listeningPulse, {
        toValue: 0,
        duration: 220,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: true,
      }).start();
      return;
    }

    listeningPulse.setValue(0);
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(listeningPulse, {
          toValue: 1,
          duration: 920,
          easing: Easing.out(Easing.cubic),
          useNativeDriver: true,
        }),
        Animated.timing(listeningPulse, {
          toValue: 0,
          duration: 780,
          easing: Easing.inOut(Easing.cubic),
          useNativeDriver: true,
        }),
      ])
    );
    loop.start();

    return () => loop.stop();
  }, [isListening, listeningPulse]);

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
    () => [styles.container, isWeb ? styles.webViewportLock : null],
    [isWeb]
  );

  const experienceStyles = useMemo(
    () => [
      styles.experiencePanel,
      chatModeOpen ? styles.experiencePanelChatMode : null,
    ],
    [chatModeOpen]
  );

  const heroHeight = modeProgress.interpolate({
    inputRange: [0, 1],
    outputRange: [620, 72],
  });

  const orbScale = modeProgress.interpolate({
    inputRange: [0, 0.52, 1],
    outputRange: [1, 0.46, 0.18],
  });

  const orbLift = modeProgress.interpolate({
    inputRange: [0, 1],
    outputRange: [0, -540],
  });

  const captionOpacity = modeProgress.interpolate({
    inputRange: [0, 1],
    outputRange: [1, 0],
  });

  const captionLift = modeProgress.interpolate({
    inputRange: [0, 1],
    outputRange: [0, -18],
  });

  const listeningRingScale = listeningPulse.interpolate({
    inputRange: [0, 1],
    outputRange: [0.96, 1.06],
  });

  const listeningRingOpacity = listeningPulse.interpolate({
    inputRange: [0, 0.5, 1],
    outputRange: [isListening ? 0.82 : 0, 0.95, 0.78],
  });

  const atlasIconOpacity = atlasProgress.interpolate({
    inputRange: [0, 0.42, 1],
    outputRange: [1, 0, 0],
  });

  const atlasCloseOpacity = atlasProgress.interpolate({
    inputRange: [0, 0.48, 1],
    outputRange: [0, 0, 1],
  });

  const atlasIconRotate = atlasProgress.interpolate({
    inputRange: [0, 1],
    outputRange: ["0deg", "-90deg"],
  });

  const atlasCloseRotate = atlasProgress.interpolate({
    inputRange: [0, 1],
    outputRange: ["90deg", "0deg"],
  });

  return (
    <SafeAreaView style={[styles.safeArea, isWeb ? styles.webViewportLock : null]}>
      <View style={shellStyles}>
        <View style={experienceStyles}>
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
                    <Animated.View
                      pointerEvents="none"
                      style={[
                        styles.speakButtonRing,
                        styles.speakButtonRingOuter,
                        {
                          opacity: listeningRingOpacity,
                          transform: [{ scale: listeningRingScale }],
                        },
                      ]}
                    />
                    <Animated.View
                      pointerEvents="none"
                      style={[
                        styles.speakButtonRing,
                        styles.speakButtonRingThird,
                        {
                          opacity: listeningRingOpacity,
                          transform: [{ scale: listeningRingScale }],
                        },
                      ]}
                    />
                    <Animated.View
                      pointerEvents="none"
                      style={[
                        styles.speakButtonRing,
                        styles.speakButtonRingSecond,
                        {
                          opacity: listeningRingOpacity,
                          transform: [{ scale: listeningRingScale }],
                        },
                      ]}
                    />
                    <Animated.View
                      pointerEvents="none"
                      style={[
                        styles.speakButtonRing,
                        styles.speakButtonRingFirst,
                        {
                          opacity: listeningRingOpacity,
                          transform: [{ scale: listeningRingScale }],
                        },
                      ]}
                    />
                    <Animated.View
                      pointerEvents="none"
                      style={[
                        styles.speakButtonInnerGlow,
                        {
                          opacity: isListening ? 1 : 0,
                        },
                      ]}
                    />
                    <Mic
                      size={23}
                      color={isListening ? "#8DEEFF" : "#EAF4FF"}
                      strokeWidth={2.2}
                    />
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
            progress={atlasProgress}
            onClose={() => setAtlasOpen(false)}
          />
        ) : null}

        {isWeb ? (
          <View pointerEvents="box-none" style={styles.atlasToggleDock}>
            <Pressable
              onPress={() => setAtlasOpen((current) => !current)}
              accessibilityRole="button"
              accessibilityLabel={atlasOpen ? "Close memory atlas" : "Open memory atlas"}
              hitSlop={10}
              style={[
                styles.atlasToggle,
                atlasOpen ? styles.atlasToggleOpen : null,
                isWeb ? ({ outlineStyle: "none", outlineWidth: 0 } as never) : null,
              ]}
            >
              <Animated.View
                pointerEvents="none"
                style={[
                  styles.atlasToggleIconLayer,
                  {
                    opacity: atlasIconOpacity,
                    transform: [{ rotate: atlasIconRotate }],
                  },
                ]}
              >
                <UserRound size={20} color="#DFF8FF" strokeWidth={2.15} />
              </Animated.View>
              <Animated.View
                pointerEvents="none"
                style={[
                  styles.atlasToggleIconLayer,
                  {
                    opacity: atlasCloseOpacity,
                    transform: [{ rotate: atlasCloseRotate }],
                  },
                ]}
              >
                <X size={22} color="#F4F8FF" strokeWidth={2.25} />
              </Animated.View>
            </Pressable>
          </View>
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
  webViewportLock: {
    height: "100vh" as never,
    maxHeight: "100vh" as never,
    overflow: "hidden",
  },
  experiencePanel: {
    flex: 1,
    minHeight: 0,
    justifyContent: "center",
    paddingHorizontal: 24,
    paddingTop: 20,
    paddingBottom: 44,
    backgroundColor: "#080B14",
    position: "relative",
    overflow: "hidden",
  },
  experiencePanelChatMode: {
    gap: 6,
    paddingTop: 22,
    paddingBottom: 16,
  },
  atlasToggleDock: {
    position: "absolute",
    top: 22,
    right: 24,
    zIndex: 120,
  },
  atlasToggle: {
    position: "relative",
    width: 44,
    height: 44,
    borderRadius: 999,
    backgroundColor: "rgba(17, 26, 43, 0.82)",
    borderWidth: 1,
    borderColor: "rgba(146,229,255,0.24)",
    justifyContent: "center",
    alignItems: "center",
    overflow: "hidden",
    shadowColor: "#84ECFF",
    shadowOpacity: 0.16,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 0 },
    zIndex: 90,
  },
  atlasToggleOpen: {
    backgroundColor: "rgba(20, 30, 49, 0.92)",
    borderColor: "rgba(244,248,255,0.28)",
  },
  atlasToggleIconLayer: {
    position: "absolute",
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    alignItems: "center",
    justifyContent: "center",
  },
  centerpiece: {
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
    width: "100%",
    alignSelf: "center",
    position: "relative",
    zIndex: 40,
  },
  orbModeShell: {
    alignItems: "center",
    justifyContent: "center",
    width: "100%",
    marginTop: 0,
    position: "relative",
    zIndex: 41,
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
    marginTop: 58,
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
    overflow: "visible",
    shadowColor: "#84ECFF",
    shadowOpacity: 0.16,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 0 },
  },
  speakButtonRing: {
    position: "absolute",
    borderRadius: 999,
    shadowColor: "#84ECFF",
    shadowOpacity: 0.18,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 0 },
  },
  speakButtonRingOuter: {
    width: 86,
    height: 86,
    left: -17,
    top: -17,
    backgroundColor: "rgba(132, 236, 255, 0.03)",
  },
  speakButtonRingThird: {
    width: 76,
    height: 76,
    left: -12,
    top: -12,
    backgroundColor: "rgba(132, 236, 255, 0.052)",
  },
  speakButtonRingSecond: {
    width: 68,
    height: 68,
    left: -8,
    top: -8,
    backgroundColor: "rgba(132, 236, 255, 0.08)",
  },
  speakButtonRingFirst: {
    width: 60,
    height: 60,
    left: -4,
    top: -4,
    backgroundColor: "rgba(132, 236, 255, 0.12)",
  },
  speakButtonInnerGlow: {
    position: "absolute",
    inset: 4,
    borderRadius: 999,
    backgroundColor: "rgba(132, 236, 255, 0.14)",
    shadowColor: "#84ECFF",
    shadowOpacity: 0.34,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 0 },
  },
  speakButtonPressed: {
    transform: [{ scale: 0.97 }],
    opacity: 0.92,
  },
  speakButtonListening: {
    borderColor: "rgba(132, 236, 255, 0.52)",
    backgroundColor: "#101A2B",
    shadowOpacity: 0.28,
    shadowRadius: 24,
  },
});
