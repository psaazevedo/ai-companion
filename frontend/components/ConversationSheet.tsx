import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import {
  MessageCircle,
  Mic,
  SendHorizontal,
} from "lucide-react-native";
import {
  Animated,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  type StyleProp,
  Text,
  TextInput,
  View,
  type ViewStyle,
} from "react-native";

import type { ConversationTurn } from "@/hooks/useConversationFeed";

const INPUT_MIN_HEIGHT = 50;
const INPUT_MAX_HEIGHT = 156;

type ConversationSheetProps = {
  visible: boolean;
  progress: Animated.Value;
  turns: ConversationTurn[];
  pendingUserText: string | null;
  responsePreview: string;
  draft: string;
  isThinking: boolean;
  isSpeaking: boolean;
  isListening: boolean;
  isLoading: boolean;
  isSending: boolean;
  error: string | null;
  onDraftChange: (value: string) => void;
  onSend: (text: string) => Promise<boolean>;
};

export function ConversationSheet({
  visible,
  progress,
  turns,
  pendingUserText,
  responsePreview,
  draft,
  isThinking,
  isSpeaking,
  isListening,
  isLoading,
  isSending,
  error,
  onDraftChange,
  onSend,
}: ConversationSheetProps) {
  const scrollRef = useRef<ScrollView | null>(null);
  const inputRef = useRef<TextInput | null>(null);
  const [inputHeight, setInputHeight] = useState(INPUT_MIN_HEIGHT);

  useEffect(() => {
    if (!visible) {
      return;
    }

    const timeout = setTimeout(() => {
      if (Platform.OS === "web" && typeof window !== "undefined") {
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
        scrollRef.current?.scrollToEnd({ animated: false });
        (inputRef.current as { focus?: (options?: FocusOptions) => void } | null)?.focus?.({
          preventScroll: true,
        });
        window.requestAnimationFrame(keepAppCanvasPinned);
        setTimeout(() => {
          scrollRef.current?.scrollToEnd({ animated: false });
          keepAppCanvasPinned();
        }, 60);
        setTimeout(() => {
          scrollRef.current?.scrollToEnd({ animated: false });
          keepAppCanvasPinned();
        }, 180);
      } else {
        scrollRef.current?.scrollToEnd({ animated: false });
        inputRef.current?.focus();
      }
    }, 120);

    return () => clearTimeout(timeout);
  }, [visible, turns, responsePreview, pendingUserText, isThinking, isSpeaking]);

  const canSend = useMemo(
    () => draft.trim().length > 0 && !isSending && !isListening,
    [draft, isListening, isSending]
  );

  const handleSend = async () => {
    const text = draft.trim();
    if (!text || isSending) {
      return;
    }

    await onSend(text);
  };

  useEffect(() => {
    if (!draft.trim()) {
      setInputHeight(INPUT_MIN_HEIGHT);
    }
  }, [draft]);

  const showEmptyState =
    !isLoading &&
    !error &&
    turns.length === 0 &&
    !pendingUserText &&
    !responsePreview;
  const latestAssistantTurn = useMemo(
    () => [...turns].reverse().find((turn) => turn.role === "assistant"),
    [turns]
  );
  const previewDuplicatesLatestTurn =
    Boolean(responsePreview.trim()) &&
    latestAssistantTurn?.text.trim() === responsePreview.trim();
  const showResponsePreview = Boolean(responsePreview.trim()) && !previewDuplicatesLatestTurn;

  return (
    <Animated.View
      pointerEvents={visible ? "auto" : "none"}
      style={[
        styles.modeShellWrap,
        Platform.OS === "web" ? styles.modeShellWrapWeb : null,
        !visible ? styles.modeShellHidden : null,
        visible ? styles.modeShellVisible : null,
        {
          opacity: progress.interpolate({
            inputRange: [0, 0.58, 1],
            outputRange: [0, 0, 1],
          }),
        },
      ]}
    >
      <View style={styles.modeShell}>
        <ScrollView
          ref={scrollRef}
          style={[
            styles.streamScroll,
            Platform.OS === "web"
              ? ({
                  overflowY: "auto",
                  overflowX: "hidden",
                  overscrollBehavior: "contain",
                  WebkitOverflowScrolling: "touch",
                } as never)
              : null,
          ]}
          contentContainerStyle={styles.streamContent}
          showsVerticalScrollIndicator={false}
        >
          {isLoading ? <Text style={styles.statusText}>Loading the thread…</Text> : null}
          {error ? <Text style={styles.errorText}>{error}</Text> : null}
          {showEmptyState ? (
            <View style={styles.emptyState}>
              <Text style={styles.emptyTitle}>The thread begins here</Text>
              <Text style={styles.emptyCopy}>
                Write something, then watch it become part of the same memory stream as voice.
              </Text>
            </View>
          ) : (
            <View style={styles.streamRail}>
              {turns.map((turn) => {
                const assistant = turn.role === "assistant";

                return (
                  <RevealRow
                    key={turn.id}
                    style={[
                      styles.storyRow,
                      assistant ? styles.storyRowAssistant : styles.storyRowUser,
                    ]}
                  >
                    <Animated.View
                      style={[
                        styles.storyCard,
                        assistant ? styles.storyCardAssistant : styles.storyCardUser,
                      ]}
                    >
                      <View style={styles.storyMeta}>
                        <Text
                          style={[
                            styles.storyRole,
                            assistant ? styles.storyRoleAssistant : styles.storyRoleUser,
                          ]}
                        >
                          {assistant ? "Companion" : "You"}
                        </Text>

                        <View style={styles.storyMetaRight}>
                          <ModeTag mode={turn.input_mode} />
                        </View>
                      </View>

                      <Text
                        style={[
                          styles.storyText,
                          assistant ? styles.storyTextAssistant : styles.storyTextUser,
                        ]}
                      >
                        {turn.text}
                      </Text>
                    </Animated.View>
                  </RevealRow>
                );
              })}

              {pendingUserText ? (
                <RevealRow style={[styles.storyRow, styles.storyRowUser]}>
                  <Animated.View
                    style={[
                      styles.storyCard,
                      styles.storyCardUser,
                      styles.storyCardPending,
                    ]}
                  >
                    <View style={styles.storyMeta}>
                      <Text style={[styles.storyRole, styles.storyRoleUser]}>You</Text>
                      <View style={styles.storyMetaRight}>
                        <ModeTag mode="text" />
                        <Text style={styles.pendingLabel}>Sending</Text>
                      </View>
                    </View>
                    <Text style={[styles.storyText, styles.storyTextUser]}>{pendingUserText}</Text>
                  </Animated.View>
                </RevealRow>
              ) : null}

              {showResponsePreview ? (
                <RevealRow style={[styles.storyRow, styles.storyRowAssistant]}>
                  <Animated.View
                    style={[
                      styles.storyCard,
                      styles.storyCardAssistant,
                      styles.storyCardPreview,
                    ]}
                  >
                    <View style={styles.storyMeta}>
                      <Text style={[styles.storyRole, styles.storyRoleAssistant]}>Companion</Text>
                      <View style={styles.storyMetaRight}>
                        <ModeTag mode={isSpeaking ? "voice" : "text"} />
                      </View>
                    </View>
                    <Text style={[styles.storyText, styles.storyTextAssistant]}>{responsePreview}</Text>
                  </Animated.View>
                </RevealRow>
              ) : null}
            </View>
          )}
        </ScrollView>
        <View pointerEvents="none" style={styles.topFade} />

        <View style={styles.composerDock}>
          <Pressable
            onPress={() => inputRef.current?.focus()}
            style={styles.composerShell}
          >
            <TextInput
              ref={inputRef}
              value={draft}
              onChangeText={onDraftChange}
              multiline
              placeholder={isListening ? "Finish speaking first…" : "Ask anything"}
              placeholderTextColor="#7488B0"
              onContentSizeChange={(event) => {
                const nextHeight = Math.min(
                  Math.max(event.nativeEvent.contentSize.height, INPUT_MIN_HEIGHT),
                  INPUT_MAX_HEIGHT
                );
                setInputHeight(nextHeight);
              }}
              style={[
                styles.input,
                { height: inputHeight },
                Platform.OS === "web"
                  ? ({ outlineStyle: "none", outlineWidth: 0 } as never)
                  : null,
              ]}
              editable={!isListening && !isSending}
              textAlignVertical="top"
              onSubmitEditing={() => {
                if (Platform.OS !== "web") {
                  return;
                }
                void handleSend();
              }}
            />

            <Pressable
              onPress={() => void handleSend()}
              disabled={!canSend}
              style={({ pressed }) => [
                styles.sendButton,
                !canSend ? styles.sendButtonDisabled : null,
                pressed && canSend ? styles.sendButtonPressed : null,
              ]}
            >
              <SendHorizontal
                size={18}
                color={canSend ? "#09101B" : "#8390A8"}
                strokeWidth={2.3}
              />
            </Pressable>
          </Pressable>
        </View>
      </View>
    </Animated.View>
  );
}

function RevealRow({
  children,
  style,
}: {
  children: ReactNode;
  style: StyleProp<ViewStyle>;
}) {
  const reveal = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.spring(reveal, {
      toValue: 1,
      damping: 19,
      stiffness: 150,
      mass: 0.78,
      useNativeDriver: true,
    }).start();
  }, [reveal]);

  return (
    <Animated.View
      style={[
        style,
        {
          opacity: reveal,
          transform: [
            {
              translateY: reveal.interpolate({
                inputRange: [0, 1],
                outputRange: [12, 0],
              }),
            },
            {
              scale: reveal.interpolate({
                inputRange: [0, 1],
                outputRange: [0.985, 1],
              }),
            },
          ],
        },
      ]}
    >
      {children}
    </Animated.View>
  );
}

function ModeTag({ mode }: { mode: "voice" | "text" | string }) {
  const voice = mode === "voice";

  return (
    <View style={[styles.modeTag, voice ? styles.modeTagVoice : styles.modeTagText]}>
      {voice ? (
        <Mic size={15} color="#AEEFFF" strokeWidth={2.2} />
      ) : (
        <MessageCircle size={15} color="#F1CCFF" strokeWidth={2.2} />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  modeShellWrap: {
    position: "absolute",
    top: 136,
    left: 0,
    right: 0,
    bottom: 112,
    width: "100%",
    maxWidth: 980,
    alignSelf: "center",
    marginTop: 0,
    paddingTop: 0,
    zIndex: 22,
  },
  modeShellWrapWeb: {
    height: "calc(100vh - 248px)" as never,
    maxHeight: "calc(100vh - 248px)" as never,
  },
  modeShellHidden: {
    display: "none",
  },
  modeShellVisible: {
    opacity: 1,
  },
  modeShell: {
    flex: 1,
    height: "100%" as never,
    minHeight: 0,
    backgroundColor: "#080B14",
    overflow: "hidden",
    position: "relative",
    flexDirection: "column",
  },
  streamScroll: {
    flex: 1,
    flexBasis: 0,
    minHeight: 0,
    flexShrink: 1,
  },
  topFade: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    height: 112,
    zIndex: 6,
    backgroundImage:
      "linear-gradient(180deg, #080B14 0%, rgba(8, 11, 20, 0.92) 28%, rgba(8, 11, 20, 0.56) 64%, rgba(8, 11, 20, 0) 100%)",
  },
  streamContent: {
    paddingHorizontal: 18,
    paddingTop: 86,
    paddingBottom: 22,
    flexGrow: 1,
  },
  statusText: {
    color: "#A8B8D9",
    fontSize: 14,
    textAlign: "center",
  },
  errorText: {
    color: "#FF9FB5",
    fontSize: 14,
    textAlign: "center",
  },
  emptyState: {
    flex: 1,
    minHeight: 240,
    alignItems: "flex-start",
    justifyContent: "center",
    paddingHorizontal: 18,
  },
  emptyTitle: {
    color: "#EEF5FF",
    fontSize: 22,
    fontWeight: "700",
  },
  emptyCopy: {
    color: "#889EC7",
    fontSize: 14,
    lineHeight: 20,
    marginTop: 8,
    maxWidth: 420,
  },
  streamRail: {
    position: "relative",
    paddingVertical: 8,
    paddingHorizontal: 4,
    gap: 16,
  },
  storyRow: {
    position: "relative",
    width: "100%",
  },
  storyRowAssistant: {
    paddingRight: "20%",
  },
  storyRowUser: {
    alignItems: "flex-end",
    paddingLeft: "34%",
  },
  storyCard: {
    minHeight: 72,
    borderRadius: 22,
    borderWidth: 1,
  },
  storyCardAssistant: {
    width: "84%",
    alignSelf: "flex-start",
    paddingHorizontal: 22,
    paddingVertical: 18,
    backgroundColor: "rgba(13, 20, 34, 0.82)",
    backgroundImage:
      "linear-gradient(135deg, rgba(25, 74, 103, 0.28) 0%, rgba(13, 20, 34, 0.82) 58%, rgba(10, 15, 27, 0.86) 100%)",
    borderColor: "rgba(132, 236, 255, 0.18)",
  },
  storyCardUser: {
    width: "66%",
    alignSelf: "flex-end",
    paddingHorizontal: 18,
    paddingVertical: 14,
    backgroundColor: "rgba(20, 17, 32, 0.82)",
    borderColor: "rgba(221, 160, 255, 0.2)",
  },
  storyCardPending: {
    borderStyle: "dashed",
    borderColor: "rgba(255, 210, 113, 0.4)",
  },
  storyCardPreview: {
    borderColor: "rgba(121, 229, 255, 0.28)",
  },
  storyMeta: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
    marginBottom: 9,
  },
  storyMetaRight: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  storyRole: {
    color: "#A8B8D9",
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.8,
    textTransform: "uppercase",
  },
  storyRoleAssistant: {
    color: "#9FEAFF",
  },
  storyRoleUser: {
    color: "#E7B5FF",
  },
  modeTag: {
    width: 30,
    height: 30,
    borderRadius: 999,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
  },
  modeTagVoice: {
    backgroundColor: "rgba(58, 112, 163, 0.14)",
    borderColor: "rgba(121, 217, 255, 0.18)",
  },
  modeTagText: {
    backgroundColor: "rgba(103, 67, 148, 0.14)",
    borderColor: "rgba(226, 150, 255, 0.14)",
  },
  storyText: {
    fontSize: 15,
    lineHeight: 22,
  },
  storyTextAssistant: {
    color: "#EAF3FF",
  },
  storyTextUser: {
    color: "#F3EFFF",
  },
  pendingLabel: {
    color: "#FFD98A",
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 0.6,
    textTransform: "uppercase",
  },
  previewLabel: {
    color: "#8CEBFF",
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 0.6,
    textTransform: "uppercase",
  },
  composerDock: {
    paddingHorizontal: 18,
    paddingBottom: 10,
    paddingTop: 10,
    backgroundColor: "#080B14",
    flexShrink: 0,
    zIndex: 8,
  },
  composerShell: {
    minHeight: 76,
    borderRadius: 22,
    paddingHorizontal: 12,
    paddingVertical: 10,
    paddingLeft: 14,
    paddingRight: 66,
    backgroundColor: "rgba(7, 12, 22, 0.78)",
    borderWidth: 1,
    borderColor: "rgba(145, 190, 255, 0.12)",
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 8,
    position: "relative",
  },
  input: {
    flex: 1,
    minHeight: 50,
    maxHeight: 156,
    borderRadius: 10,
    backgroundColor: "transparent",
    borderWidth: 0,
    color: "#EDF4FF",
    paddingHorizontal: 0,
    paddingTop: 9,
    paddingBottom: 9,
    fontSize: 15,
    lineHeight: 21,
  },
  sendButton: {
    position: "absolute",
    right: 12,
    bottom: 16,
    width: 44,
    height: 44,
    borderRadius: 999,
    backgroundColor: "rgba(231, 244, 255, 0.92)",
    alignItems: "center",
    justifyContent: "center",
  },
  sendButtonDisabled: {
    backgroundColor: "rgba(52, 62, 82, 0.72)",
  },
  sendButtonPressed: {
    transform: [{ scale: 0.98 }],
  },
});
