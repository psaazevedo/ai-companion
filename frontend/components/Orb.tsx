import { useEffect, useRef } from "react";
import { Animated, Easing, StyleSheet, View } from "react-native";

type OrbProps = {
  isListening: boolean;
  isSpeaking: boolean;
  isThinking: boolean;
  variant?: "hero" | "compact";
  modeProgress?: number;
  insightOpen?: boolean;
};

export function Orb({
  isListening,
  isSpeaking,
  isThinking,
  variant = "hero",
}: OrbProps) {
  const pulse = useRef(new Animated.Value(0)).current;
  const shimmer = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    let pulseLoop: Animated.CompositeAnimation | undefined;
    let shimmerLoop: Animated.CompositeAnimation | undefined;

    const pulseTo = isListening ? 1.0 : isSpeaking ? 0.8 : isThinking ? 0.55 : 0.35;
    const shimmerDuration = isSpeaking ? 700 : isThinking ? 1200 : 2400;

    pulseLoop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, {
          toValue: pulseTo,
          duration: 900,
          easing: Easing.inOut(Easing.quad),
          useNativeDriver: true,
        }),
        Animated.timing(pulse, {
          toValue: 0.15,
          duration: 900,
          easing: Easing.inOut(Easing.quad),
          useNativeDriver: true,
        }),
      ])
    );

    shimmerLoop = Animated.loop(
      Animated.timing(shimmer, {
        toValue: 1,
        duration: shimmerDuration,
        easing: Easing.inOut(Easing.sin),
        useNativeDriver: true,
      })
    );

    pulse.setValue(0.15);
    shimmer.setValue(0);
    pulseLoop.start();
    shimmerLoop.start();

    return () => {
      pulseLoop?.stop();
      shimmerLoop?.stop();
    };
  }, [isListening, isSpeaking, isThinking, pulse, shimmer]);

  const scale = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [0.96, 1.1],
  });

  const haloScale = shimmer.interpolate({
    inputRange: [0, 1],
    outputRange: [1, 1.25],
  });

  const haloOpacity = shimmer.interpolate({
    inputRange: [0, 1],
    outputRange: [0.22, 0.04],
  });

  const coreColor = isListening
    ? "#76B6FF"
    : isSpeaking
      ? "#8DE7C2"
      : isThinking
        ? "#FFC785"
        : "#EAF1FF";

  return (
    <View style={[styles.frame, variant === "compact" ? styles.frameCompact : null]}>
      <Animated.View
        style={[
          styles.halo,
          variant === "compact" ? styles.haloCompact : null,
          {
            backgroundColor: coreColor,
            opacity: haloOpacity,
            transform: [{ scale: haloScale }],
          },
        ]}
      />
      <Animated.View
        style={[
          styles.core,
          variant === "compact" ? styles.coreCompact : null,
          {
            backgroundColor: coreColor,
            transform: [{ scale }],
          },
        ]}
      />
      <View style={[styles.innerShadow, variant === "compact" ? styles.innerShadowCompact : null]} />
    </View>
  );
}

const styles = StyleSheet.create({
  frame: {
    width: 220,
    height: 220,
    alignItems: "center",
    justifyContent: "center",
  },
  frameCompact: {
    width: 112,
    height: 112,
  },
  halo: {
    position: "absolute",
    width: 220,
    height: 220,
    borderRadius: 999,
  },
  haloCompact: {
    width: 112,
    height: 112,
  },
  core: {
    width: 128,
    height: 128,
    borderRadius: 999,
    shadowColor: "#9BC5FF",
    shadowOpacity: 0.6,
    shadowRadius: 36,
    shadowOffset: { width: 0, height: 0 },
  },
  coreCompact: {
    width: 62,
    height: 62,
    shadowRadius: 18,
  },
  innerShadow: {
    position: "absolute",
    width: 104,
    height: 104,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.22)",
  },
  innerShadowCompact: {
    width: 52,
    height: 52,
  },
});
