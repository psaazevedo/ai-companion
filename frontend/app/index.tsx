import { useEffect, useMemo, useRef, useState } from "react";
import {
  Animated,
  Easing,
  Platform,
  SafeAreaView,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
} from "react-native";

import { AtlasToggle } from "@/components/AtlasToggle";
import { ConversationSheet } from "@/components/ConversationSheet";
import { MemoryInspector } from "@/components/MemoryInspector";
import { ModeToggle } from "@/components/ModeToggle";
import { Notification } from "@/components/Notification";
import { Orb } from "@/components/Orb";
import {
  VoiceActionButton,
  VoiceActionButtonSpacer,
} from "@/components/VoiceActionButton";
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
  const { height: viewportHeight, width: viewportWidth } = useWindowDimensions();
  const compactViewport = viewportWidth < 720 || viewportHeight < 760;
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

  const voiceHeroHeight = Math.min(620, Math.max(compactViewport ? 360 : 420, viewportHeight * 0.58));
  const chatHeroHeight = compactViewport ? 156 : 164;
  const chatOrbTargetY = compactViewport ? 132 : 124;
  const chatOrbLift = -Math.max(0, viewportHeight * 0.5 - chatOrbTargetY);

  const heroHeight = modeProgress.interpolate({
    inputRange: [0, 1],
    outputRange: [voiceHeroHeight, chatHeroHeight],
  });

  const orbScale = modeProgress.interpolate({
    inputRange: [0, 0.52, 1],
    outputRange: [1, 0.48, compactViewport ? 0.32 : 0.24],
  });

  const orbLift = modeProgress.interpolate({
    inputRange: [0, 1],
    outputRange: [0, chatOrbLift],
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
          </Animated.View>

          {responsePreview && !isListening && !chatModeOpen ? (
            <Animated.View
              pointerEvents="none"
              style={[
                styles.responsePreviewDock,
                compactViewport ? styles.responsePreviewDockCompact : null,
                {
                  opacity: captionOpacity,
                  transform: [{ translateY: captionLift }],
                },
              ]}
            >
              <Text style={styles.responsePreview} numberOfLines={3}>
                {responsePreview}
              </Text>
            </Animated.View>
          ) : null}

          <Animated.View
            pointerEvents="none"
            style={[
              styles.chatTopCanopy,
              compactViewport ? styles.chatTopCanopyCompact : null,
              {
                opacity: modeProgress.interpolate({
                  inputRange: [0, 0.36, 1],
                  outputRange: [0, 0.48, 1],
                }),
              },
            ]}
          />

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

          <Animated.View style={styles.footer}>
            <View style={styles.actionStack}>
              {!chatModeOpen ? (
                <VoiceActionButton
                  isListening={isListening}
                  listeningPulse={listeningPulse}
                  modeProgress={modeProgress}
                  onPressIn={startListening}
                  onPressOut={stopListening}
                />
              ) : (
                <VoiceActionButtonSpacer />
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
          <AtlasToggle
            isOpen={atlasOpen}
            progress={atlasProgress}
            onToggle={() => setAtlasOpen((current) => !current)}
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
  centerpiece: {
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
    width: "100%",
    alignSelf: "center",
    position: "relative",
    zIndex: 40,
  },
  chatTopCanopy: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    height: 330,
    zIndex: 28,
    backgroundImage:
      "linear-gradient(180deg, rgba(8, 11, 20, 0.98) 0%, rgba(9, 16, 29, 0.9) 30%, rgba(9, 16, 29, 0.54) 58%, rgba(8, 11, 20, 0.16) 82%, rgba(8, 11, 20, 0) 100%)",
  },
  chatTopCanopyCompact: {
    height: 250,
    backgroundImage:
      "linear-gradient(180deg, rgba(8, 11, 20, 0.98) 0%, rgba(9, 16, 29, 0.88) 32%, rgba(9, 16, 29, 0.48) 62%, rgba(8, 11, 20, 0.12) 84%, rgba(8, 11, 20, 0) 100%)",
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
    maxWidth: 720,
    color: "#C7D5F3",
    fontSize: 18,
    lineHeight: 27,
    textAlign: "center",
  },
  responsePreviewDock: {
    position: "absolute",
    left: 24,
    right: 24,
    bottom: 156,
    alignItems: "center",
    zIndex: 26,
  },
  responsePreviewDockCompact: {
    bottom: 144,
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
});
