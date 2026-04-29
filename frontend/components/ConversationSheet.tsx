import { useEffect, useMemo, useRef, useState } from "react";
import {
  SendHorizontal,
} from "lucide-react-native";
import {
  Animated,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  useWindowDimensions,
} from "react-native";

import type { ConversationTurn } from "@/hooks/useConversationFeed";

const INPUT_MIN_HEIGHT = 50;
const INPUT_MAX_HEIGHT = 156;
const LENS_MIN_ITEM_HEIGHT = 300;
const LENS_MAX_ITEM_HEIGHT = 1280;
const LENS_PROMPT_CHARS_PER_LINE = 34;
const LENS_ANSWER_CHARS_PER_LINE = 68;

type LensPair = {
  id: string;
  question: string;
  answer: string;
  status?: "pending" | "streaming";
};

type LensLayoutItem = {
  height: number;
  offset: number;
  center: number;
};

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
  const { height: viewportHeight, width: viewportWidth } = useWindowDimensions();
  const compactViewport = viewportWidth < 720 || viewportHeight < 760;
  const scrollRef = useRef<ScrollView | null>(null);
  const inputRef = useRef<TextInput | null>(null);
  const lensScrollY = useRef(new Animated.Value(0)).current;
  const [inputHeight, setInputHeight] = useState(INPUT_MIN_HEIGHT);
  const [activeLensIndex, setActiveLensIndex] = useState(0);
  const [scrollViewportHeight, setScrollViewportHeight] = useState(0);

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
        (inputRef.current as { focus?: (options?: FocusOptions) => void } | null)?.focus?.({
          preventScroll: true,
        });
        window.requestAnimationFrame(keepAppCanvasPinned);
        setTimeout(() => {
          keepAppCanvasPinned();
        }, 60);
        setTimeout(() => {
          keepAppCanvasPinned();
        }, 180);
      } else {
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
  const lensPairs = useMemo<LensPair[]>(() => {
    const pairs: LensPair[] = [];
    let openPair: LensPair | null = null;

    turns.forEach((turn) => {
      if (turn.role === "user") {
        if (openPair) {
          pairs.push(openPair);
        }
        openPair = {
          id: turn.id,
          question: turn.text,
          answer: "",
        };
        return;
      }

      if (openPair && !openPair.answer) {
        openPair = {
          ...openPair,
          id: `${openPair.id}:${turn.id}`,
          answer: turn.text,
        };
        pairs.push(openPair);
        openPair = null;
        return;
      }

      pairs.push({
        id: turn.id,
        question: "Companion offered",
        answer: turn.text,
      });
    });

    if (openPair) {
      pairs.push(openPair);
    }

    if (pendingUserText) {
      pairs.push({
        id: `pending:${pendingUserText}`,
        question: pendingUserText,
        answer: "Listening for the shape of the answer…",
        status: "pending",
      });
    }

    if (showResponsePreview) {
      const lastPair = pairs[pairs.length - 1];
      if (lastPair && !lastPair.answer) {
        pairs[pairs.length - 1] = {
          ...lastPair,
          answer: responsePreview,
          status: isSpeaking ? "streaming" : undefined,
        };
      } else if (!lastPair || lastPair.answer.trim() !== responsePreview.trim()) {
        pairs.push({
          id: `preview:${responsePreview}`,
          question: "Companion is forming",
          answer: responsePreview,
          status: isSpeaking ? "streaming" : undefined,
        });
      }
    }

    return pairs;
  }, [isSpeaking, pendingUserText, responsePreview, showResponsePreview, turns]);

  const sheetTop = compactViewport ? 96 : 136;
  const sheetBottom = compactViewport ? 96 : 112;
  const streamPaddingTop = compactViewport ? 58 : 96;
  const streamPaddingBottom = compactViewport ? 164 : 210;
  const lensItemGap = compactViewport ? 72 : 88;
  const lensLayout = useMemo(
    () => buildLensLayout(lensPairs, viewportWidth, viewportHeight, lensItemGap),
    [lensItemGap, lensPairs, viewportHeight, viewportWidth]
  );
  const lensFocusY =
    scrollViewportHeight > 0
      ? compactViewport
        ? Math.min(
            Math.max(300, scrollViewportHeight * 0.52),
            Math.max(320, scrollViewportHeight - streamPaddingBottom - 120)
          )
        : Math.min(430, Math.max(320, scrollViewportHeight * 0.5))
      : compactViewport
        ? 300
        : 430;
  const firstLayout = lensLayout[0];
  const lensTopSpacer = Math.max(
    compactViewport ? 24 : 72,
    Math.round(lensFocusY - streamPaddingTop - (firstLayout?.height ?? LENS_MIN_ITEM_HEIGHT) / 2)
  );
  const lensBottomSpacer = useMemo(() => {
    const lastLayout = lensLayout[lensLayout.length - 1];
    if (!lastLayout || scrollViewportHeight <= 0) {
      return 0;
    }

    return Math.max(
      0,
      scrollViewportHeight -
        lensFocusY -
        streamPaddingBottom -
        lastLayout.height / 2
    );
  }, [lensFocusY, lensLayout, scrollViewportHeight, streamPaddingBottom]);
  const lensContentHeight =
    lensLayout.length > 0
      ? lensTopSpacer +
        lensLayout[lensLayout.length - 1].offset +
        lensLayout[lensLayout.length - 1].height +
        lensBottomSpacer
      : LENS_MIN_ITEM_HEIGHT;

  useEffect(() => {
    if (!visible || lensPairs.length === 0) {
      return;
    }
    const latestIndex = lensPairs.length - 1;
    const latestLayout = lensLayout[latestIndex];
    const latestOffset = latestLayout
      ? getLensScrollTarget(latestLayout, lensTopSpacer, lensFocusY, streamPaddingTop)
      : 0;
    setActiveLensIndex(latestIndex);
    lensScrollY.setValue(latestOffset);

    const timeout = setTimeout(() => {
      scrollRef.current?.scrollTo({
        y: Math.max(0, latestOffset),
        animated: false,
      });
    }, 230);

    return () => clearTimeout(timeout);
  }, [lensFocusY, lensLayout, lensPairs.length, lensScrollY, lensTopSpacer, streamPaddingTop, visible]);

  return (
    <Animated.View
      pointerEvents={visible ? "auto" : "none"}
      style={[
        styles.modeShellWrap,
        { top: sheetTop, bottom: sheetBottom },
        Platform.OS === "web"
          ? ({
              height: Math.max(240, viewportHeight - sheetTop - sheetBottom),
              maxHeight: Math.max(240, viewportHeight - sheetTop - sheetBottom),
            } as never)
          : null,
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
        <View pointerEvents="none" style={styles.lensField}>
          <View style={styles.lensAxis} />
          <View style={[styles.lensParticle, styles.lensParticleOne]} />
          <View style={[styles.lensParticle, styles.lensParticleTwo]} />
          <View style={[styles.lensParticle, styles.lensParticleThree]} />
        </View>
        <ScrollView
          ref={scrollRef}
          onLayout={(event) => {
            setScrollViewportHeight(event.nativeEvent.layout.height);
          }}
          onScroll={Animated.event(
            [{ nativeEvent: { contentOffset: { y: lensScrollY } } }],
            {
              useNativeDriver: true,
              listener: (event: { nativeEvent: { contentOffset: { y: number } } }) => {
                const y = event.nativeEvent.contentOffset.y;
                const focusY = y + lensFocusY - streamPaddingTop;
                const nextIndex = Math.max(
                  0,
                  Math.min(
                    lensPairs.length - 1,
                    findClosestLensIndex(lensLayout, focusY, lensTopSpacer)
                  )
                );
                if (nextIndex !== activeLensIndex) {
                  setActiveLensIndex(nextIndex);
                }
              },
            }
          )}
          scrollEventThrottle={16}
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
          contentContainerStyle={[
            styles.streamContent,
            {
              paddingTop: streamPaddingTop,
              paddingBottom: streamPaddingBottom,
            },
          ]}
          showsVerticalScrollIndicator={false}
        >
          {isLoading ? <Text style={styles.statusText}>Loading the thread…</Text> : null}
          {error ? <Text style={styles.errorText}>{error}</Text> : null}
          {showEmptyState || lensPairs.length === 0 ? (
            <View style={styles.emptyState}>
              <Text style={styles.emptyTitle}>The thread begins here</Text>
              <Text style={styles.emptyCopy}>
                Write something, then watch it become part of the same memory stream as voice.
              </Text>
            </View>
          ) : (
            <View
              style={[
                styles.lensStack,
                { height: Math.max(lensContentHeight, LENS_MIN_ITEM_HEIGHT) },
              ]}
            >
              {lensPairs.map((pair, index) => {
                const layout = lensLayout[index];
                if (!layout || Math.abs(index - activeLensIndex) > 2) {
                  return null;
                }

                return (
                  <LensPairView
                    key={pair.id}
                    pair={pair}
                    index={index}
                    activeIndex={activeLensIndex}
                    scrollY={lensScrollY}
                    layout={layout}
                    compactViewport={compactViewport}
                    previousCenter={
                      lensTopSpacer +
                      (lensLayout[index - 1]?.center ?? layout.center - layout.height)
                    }
                    nextCenter={
                      lensTopSpacer +
                      (lensLayout[index + 1]?.center ?? layout.center + layout.height)
                    }
                    lensTopSpacer={lensTopSpacer}
                    lensFocusY={lensFocusY}
                    streamPaddingTop={streamPaddingTop}
                  />
                );
              })}
            </View>
          )}
        </ScrollView>
        <View pointerEvents="none" style={styles.topFade} />

        <View style={[styles.composerDock, compactViewport ? styles.composerDockCompact : null]}>
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

function LensPairView({
  pair,
  index,
  activeIndex,
  scrollY,
  layout,
  compactViewport,
  previousCenter,
  nextCenter,
  lensTopSpacer,
  lensFocusY,
  streamPaddingTop,
}: {
  pair: LensPair;
  index: number;
  activeIndex: number;
  scrollY: Animated.Value;
  layout: LensLayoutItem;
  compactViewport: boolean;
  previousCenter: number;
  nextCenter: number;
  lensTopSpacer: number;
  lensFocusY: number;
  streamPaddingTop: number;
}) {
  const reveal = useRef(new Animated.Value(0)).current;
  const active = index === activeIndex;
  const holdStart = lensTopSpacer + layout.offset + layout.height * 0.18;
  const holdEnd = lensTopSpacer + layout.offset + layout.height * 0.82;
  const focusPosition = Animated.add(scrollY, lensFocusY - streamPaddingTop);
  const scrollFocus = focusPosition.interpolate({
    inputRange: [
      previousCenter,
      holdStart,
      holdEnd,
      nextCenter,
    ],
    outputRange: [0, 1, 1, 0],
    extrapolate: "clamp",
  });

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
        styles.lensItem,
        compactViewport ? styles.lensItemCompact : null,
        {
          top: lensTopSpacer + layout.offset,
          height: layout.height,
          opacity: scrollFocus.interpolate({
            inputRange: [0, 0.5, 1],
            outputRange: [0.26, 0.56, 1],
          }),
          transform: [
            {
              translateY: reveal.interpolate({
                inputRange: [0, 1],
                outputRange: [12, 0],
              }),
            },
            {
              scale: scrollFocus.interpolate({
                inputRange: [0, 0.5, 1],
                outputRange: [0.68, 0.84, 1],
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
      <View style={[styles.lensExchange, compactViewport ? styles.lensExchangeCompact : null]}>
        <View style={[styles.lensPromptPill, compactViewport ? styles.lensPromptPillCompact : null]}>
          <Text style={[styles.lensQuestion, compactViewport ? styles.lensQuestionCompact : null]}>
            {pair.question}
          </Text>
          {active && pair.status ? (
            <Text style={styles.lensStatus}>{pair.status}</Text>
          ) : null}
        </View>
        <View style={styles.lensConnector} />
        <View style={[styles.lensAnswerPanel, compactViewport ? styles.lensAnswerPanelCompact : null]}>
          <Text style={[styles.lensAnswer, compactViewport ? styles.lensAnswerCompact : null]}>
            {pair.answer || "Still forming the answer…"}
          </Text>
        </View>
      </View>
    </Animated.View>
  );
}

function buildLensLayout(
  pairs: LensPair[],
  viewportWidth: number,
  viewportHeight: number,
  itemGap: number
): LensLayoutItem[] {
  let offset = 0;

  return pairs.map((pair) => {
    const height = estimateLensItemHeight(pair, viewportWidth, viewportHeight);
    const item = {
      height,
      offset,
      center: offset + height / 2,
    };
    offset += height + itemGap;
    return item;
  });
}

function estimateLensItemHeight(
  pair: LensPair,
  viewportWidth: number,
  viewportHeight: number
) {
  const compact = viewportWidth < 720 || viewportHeight < 760;
  const promptCharsPerLine = compact ? 24 : LENS_PROMPT_CHARS_PER_LINE;
  const answerCharsPerLine = compact
    ? Math.max(30, Math.floor(viewportWidth / 16))
    : LENS_ANSWER_CHARS_PER_LINE;
  const minHeight = compact ? 260 : LENS_MIN_ITEM_HEIGHT;
  const maxHeight = Math.max(
    compact ? 620 : 760,
    Math.min(compact ? 1180 : LENS_MAX_ITEM_HEIGHT, viewportHeight * (compact ? 1.35 : 1.42))
  );
  const questionLines = Math.max(
    1,
    Math.ceil(pair.question.trim().length / promptCharsPerLine)
  );
  const answerText = (pair.answer || "Still forming the answer…").trim();
  const answerLines = Math.max(2, Math.ceil(answerText.length / answerCharsPerLine));
  const contentHeight = (compact ? 118 : 126) + questionLines * 20 + answerLines * (compact ? 24 : 25);
  return Math.min(Math.max(contentHeight, minHeight), maxHeight);
}

function getLensScrollTarget(
  item: LensLayoutItem,
  lensTopSpacer: number,
  lensFocusY: number,
  streamPaddingTop: number
) {
  return Math.max(
    0,
    lensTopSpacer + item.center - (lensFocusY - streamPaddingTop)
  );
}

function findClosestLensIndex(layout: LensLayoutItem[], y: number, lensTopSpacer: number) {
  if (layout.length === 0) {
    return 0;
  }

  let closestIndex = 0;
  let closestDistance = Number.POSITIVE_INFINITY;

  layout.forEach((item, index) => {
    const holdStart = lensTopSpacer + item.offset + item.height * 0.18;
    const holdEnd = lensTopSpacer + item.offset + item.height * 0.82;
    const distance =
      y >= holdStart && y <= holdEnd
        ? 0
        : Math.min(Math.abs(y - holdStart), Math.abs(y - holdEnd));

    if (distance < closestDistance) {
      closestDistance = distance;
      closestIndex = index;
    }
  });

  return closestIndex;
}

const styles = StyleSheet.create({
  modeShellWrap: {
    position: "absolute",
    top: 136,
    left: 0,
    right: 0,
    bottom: 112,
    width: "100%",
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
  lensField: {
    position: "absolute",
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    zIndex: 0,
  },
  lensAura: {
    position: "absolute",
    top: -12,
    left: 0,
    right: 0,
    height: 420,
    backgroundImage:
      "radial-gradient(ellipse at 50% 0%, rgba(43, 120, 158, 0.09) 0%, rgba(15, 31, 56, 0.045) 44%, rgba(8, 11, 20, 0.01) 70%, rgba(8, 11, 20, 0) 100%)",
  },
  lensAxis: {
    position: "absolute",
    top: 28,
    bottom: 86,
    left: "50%",
    width: 1,
    backgroundImage:
      "linear-gradient(180deg, rgba(139, 231, 255, 0), rgba(139, 231, 255, 0.1) 28%, rgba(139, 231, 255, 0.015) 45%, rgba(226, 143, 255, 0.015) 58%, rgba(139, 231, 255, 0.08) 76%, rgba(139, 231, 255, 0))",
  },
  lensParticle: {
    position: "absolute",
    width: 5,
    height: 5,
    borderRadius: 999,
    backgroundColor: "rgba(139, 231, 255, 0.42)",
    shadowColor: "#8BE7FF",
    shadowOpacity: 0.34,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 0 },
  },
  lensParticleOne: {
    top: 118,
    left: "18%",
    opacity: 0.52,
  },
  lensParticleTwo: {
    top: 286,
    right: "16%",
    opacity: 0.3,
    backgroundColor: "rgba(226, 143, 255, 0.52)",
  },
  lensParticleThree: {
    bottom: 144,
    left: "49%",
    opacity: 0.26,
  },
  streamScroll: {
    flex: 1,
    flexBasis: 0,
    minHeight: 0,
    flexShrink: 1,
    zIndex: 2,
  },
  topFade: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    height: 300,
    zIndex: 30,
    backgroundImage:
      "linear-gradient(180deg, rgba(8, 11, 20, 0.94) 0%, rgba(8, 11, 20, 0.72) 30%, rgba(8, 11, 20, 0.34) 62%, rgba(8, 11, 20, 0.08) 86%, rgba(8, 11, 20, 0) 100%)",
  },
  streamContent: {
    paddingHorizontal: 18,
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
    paddingTop: 28,
    paddingBottom: 12,
    paddingHorizontal: 4,
    gap: 28,
  },
  lensStack: {
    paddingTop: 0,
    paddingBottom: 14,
    position: "relative",
  },
  lensItem: {
    position: "absolute",
    left: 0,
    right: 0,
    width: "100%",
    alignSelf: "center",
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 22,
  },
  lensItemCompact: {
    paddingHorizontal: 8,
  },
  lensExchange: {
    width: "78%",
    maxWidth: 680,
    minHeight: 190,
    alignItems: "center",
    justifyContent: "center",
  },
  lensExchangeCompact: {
    width: "94%",
  },
  lensCard: {
    width: "88%",
    maxWidth: 680,
    minHeight: 180,
    borderRadius: 32,
    paddingHorizontal: 24,
    paddingVertical: 22,
    borderWidth: 1,
    borderColor: "rgba(139, 231, 255, 0.14)",
    backgroundColor: "rgba(8, 12, 23, 0.58)",
    shadowColor: "#70E5FF",
    shadowOpacity: 0.08,
    shadowRadius: 34,
    shadowOffset: { width: 0, height: 0 },
  },
  lensCardActive: {
    borderColor: "rgba(139, 231, 255, 0.25)",
    minHeight: 224,
    backgroundImage:
      "linear-gradient(135deg, rgba(14, 39, 61, 0.72), rgba(10, 14, 25, 0.88) 52%, rgba(34, 18, 50, 0.62))",
    shadowOpacity: 0.16,
  },
  lensCardDormant: {
    maxWidth: 560,
    minHeight: 134,
    paddingHorizontal: 20,
    paddingVertical: 18,
    borderColor: "rgba(139, 231, 255, 0.08)",
    backgroundColor: "rgba(8, 12, 23, 0.3)",
  },
  lensPromptPill: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    alignSelf: "center",
    maxWidth: "76%",
    paddingHorizontal: 22,
    paddingVertical: 9,
    borderRadius: 26,
    backgroundColor: "rgba(35, 22, 50, 0.96)",
    borderWidth: 1,
    borderColor: "rgba(226, 143, 255, 0.18)",
  },
  lensPromptPillCompact: {
    maxWidth: "96%",
    paddingHorizontal: 18,
    paddingVertical: 10,
    borderRadius: 22,
  },
  lensKicker: {
    color: "#A9B8D3",
    fontSize: 9,
    fontWeight: "800",
    letterSpacing: 1.8,
    textTransform: "uppercase",
    marginBottom: 0,
  },
  lensKickerActive: {
    color: "#E8B9FF",
  },
  lensKickerCompanion: {
    color: "#93EAFF",
    marginBottom: 8,
  },
  lensStatus: {
    color: "#7387AA",
    fontSize: 9,
    fontWeight: "800",
    letterSpacing: 1.5,
    textTransform: "uppercase",
    marginTop: 4,
  },
  lensQuestion: {
    color: "#F1D9FF",
    flex: 1,
    fontSize: 13,
    lineHeight: 18,
    fontWeight: "600",
    textAlign: "center",
  },
  lensQuestionCompact: {
    flexShrink: 1,
    fontSize: 13,
    lineHeight: 19,
  },
  lensConnector: {
    width: 1,
    height: 22,
    alignSelf: "center",
    backgroundImage:
      "linear-gradient(180deg, rgba(226, 143, 255, 0.34), rgba(139, 231, 255, 0.24), rgba(139, 231, 255, 0))",
    opacity: 0.78,
    shadowColor: "#8BE7FF",
    shadowOpacity: 0.24,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 0 },
  },
  lensAnswerPanel: {
    width: "92%",
    alignSelf: "center",
    minHeight: 104,
    borderRadius: 26,
    paddingHorizontal: 20,
    paddingVertical: 17,
    backgroundColor: "rgba(6, 11, 21, 0.95)",
    borderWidth: 1,
    borderColor: "rgba(139, 231, 255, 0.2)",
    backgroundImage:
      "linear-gradient(135deg, rgba(12, 28, 45, 0.4), rgba(7, 11, 20, 0.76) 68%, rgba(52, 30, 72, 0.16))",
    shadowColor: "#70E5FF",
    shadowOpacity: 0.08,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 0 },
  },
  lensAnswerPanelCompact: {
    width: "96%",
    paddingHorizontal: 18,
    paddingVertical: 16,
  },
  lensAnswer: {
    color: "#F3F8FF",
    fontSize: 16,
    lineHeight: 23,
    fontWeight: "500",
    letterSpacing: -0.3,
  },
  lensAnswerCompact: {
    fontSize: 15,
    lineHeight: 22,
  },
  lensFootnotes: {
    position: "absolute",
    left: 98,
    bottom: 16,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  lensFootnote: {
    color: "#7F93B9",
    fontSize: 10,
    fontWeight: "800",
    letterSpacing: 1.5,
    textTransform: "uppercase",
  },
  lensFootnoteDot: {
    color: "#42526F",
    fontSize: 10,
  },
  signalSpine: {
    position: "absolute",
    top: 0,
    bottom: 18,
    left: "50%",
    width: 32,
    marginLeft: -16,
    backgroundImage:
      "linear-gradient(180deg, rgba(132, 236, 255, 0), rgba(132, 236, 255, 0.1), rgba(226, 143, 255, 0.07), rgba(132, 236, 255, 0))",
  },
  storyRow: {
    position: "relative",
    width: "100%",
    minHeight: 76,
  },
  storyRowAssistant: {
    paddingRight: "30%",
  },
  storyRowUser: {
    alignItems: "flex-end",
    paddingLeft: "42%",
  },
  thoughtPin: {
    position: "absolute",
    top: 28,
    left: "50%",
    width: 9,
    height: 9,
    marginLeft: -4,
    borderRadius: 999,
    borderWidth: 1,
    zIndex: 3,
  },
  thoughtPinAssistant: {
    backgroundColor: "rgba(133, 234, 255, 0.22)",
    borderColor: "rgba(133, 234, 255, 0.46)",
    shadowColor: "#84ECFF",
    shadowOpacity: 0.32,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 0 },
  },
  thoughtPinUser: {
    backgroundColor: "rgba(222, 143, 255, 0.2)",
    borderColor: "rgba(222, 143, 255, 0.42)",
    shadowColor: "#DD8FFF",
    shadowOpacity: 0.24,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 0 },
  },
  storyCard: {
    minHeight: 68,
    borderRadius: 0,
    borderWidth: 0,
    position: "relative",
    overflow: "visible",
  },
  storyCardAssistant: {
    width: "68%",
    alignSelf: "flex-start",
    paddingHorizontal: 28,
    paddingVertical: 16,
    borderLeftWidth: 1,
    borderLeftColor: "rgba(132, 236, 255, 0.28)",
    shadowColor: "#54D8FF",
    shadowOpacity: 0.06,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 0 },
  },
  storyCardUser: {
    width: "48%",
    alignSelf: "flex-end",
    paddingHorizontal: 24,
    paddingVertical: 14,
    borderRightWidth: 1,
    borderRightColor: "rgba(221, 160, 255, 0.26)",
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
    marginBottom: 8,
  },
  storyRole: {
    color: "#A8B8D9",
    fontSize: 9,
    fontWeight: "700",
    letterSpacing: 1.8,
    textTransform: "uppercase",
  },
  storyRoleAssistant: {
    color: "#9FEAFF",
  },
  storyRoleUser: {
    color: "#E7B5FF",
  },
  storyText: {
    fontSize: 17,
    lineHeight: 25,
    fontWeight: "500",
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
    width: "78%",
    maxWidth: 680,
    minWidth: 0,
    alignSelf: "center",
    paddingBottom: 10,
    paddingTop: 10,
    backgroundColor: "#080B14",
    flexShrink: 0,
    zIndex: 8,
  },
  composerDockCompact: {
    width: "94%",
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
