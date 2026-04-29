import { Mic } from "lucide-react-native";
import { Animated, Pressable, StyleSheet, View } from "react-native";

type VoiceActionButtonProps = {
  isListening: boolean;
  modeProgress: Animated.Value;
  listeningPulse: Animated.Value;
  onPressIn: () => void;
  onPressOut: () => void;
};

export function VoiceActionButton({
  isListening,
  modeProgress,
  listeningPulse,
  onPressIn,
  onPressOut,
}: VoiceActionButtonProps) {
  const listeningRingScale = listeningPulse.interpolate({
    inputRange: [0, 1],
    outputRange: [0.96, 1.06],
  });

  const listeningRingOpacity = listeningPulse.interpolate({
    inputRange: [0, 0.5, 1],
    outputRange: [isListening ? 0.82 : 0, 0.95, 0.78],
  });

  return (
    <Animated.View
      style={[
        styles.wrap,
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
        onPressIn={onPressIn}
        onPressOut={onPressOut}
        style={({ pressed }) => [
          styles.button,
          pressed ? styles.buttonPressed : null,
          isListening ? styles.buttonListening : null,
        ]}
      >
        <PulseRing
          opacity={listeningRingOpacity}
          scale={listeningRingScale}
          style={styles.ringOuter}
        />
        <PulseRing
          opacity={listeningRingOpacity}
          scale={listeningRingScale}
          style={styles.ringThird}
        />
        <PulseRing
          opacity={listeningRingOpacity}
          scale={listeningRingScale}
          style={styles.ringSecond}
        />
        <PulseRing
          opacity={listeningRingOpacity}
          scale={listeningRingScale}
          style={styles.ringFirst}
        />
        <Animated.View
          pointerEvents="none"
          style={[
            styles.innerGlow,
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
  );
}

function PulseRing({
  opacity,
  scale,
  style,
}: {
  opacity: Animated.AnimatedInterpolation<number>;
  scale: Animated.AnimatedInterpolation<number>;
  style: object;
}) {
  return (
    <Animated.View
      pointerEvents="none"
      style={[
        styles.ring,
        style,
        {
          opacity,
          transform: [{ scale }],
        },
      ]}
    />
  );
}

export function VoiceActionButtonSpacer() {
  return <View style={styles.spacer} />;
}

const styles = StyleSheet.create({
  wrap: {
    height: 52,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 26,
  },
  spacer: {
    height: 78,
  },
  button: {
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
  ring: {
    position: "absolute",
    borderRadius: 999,
    shadowColor: "#84ECFF",
    shadowOpacity: 0.18,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 0 },
  },
  ringOuter: {
    width: 86,
    height: 86,
    left: -17,
    top: -17,
    backgroundColor: "rgba(132, 236, 255, 0.03)",
  },
  ringThird: {
    width: 76,
    height: 76,
    left: -12,
    top: -12,
    backgroundColor: "rgba(132, 236, 255, 0.052)",
  },
  ringSecond: {
    width: 68,
    height: 68,
    left: -8,
    top: -8,
    backgroundColor: "rgba(132, 236, 255, 0.08)",
  },
  ringFirst: {
    width: 60,
    height: 60,
    left: -4,
    top: -4,
    backgroundColor: "rgba(132, 236, 255, 0.12)",
  },
  innerGlow: {
    position: "absolute",
    inset: 4,
    borderRadius: 999,
    backgroundColor: "rgba(132, 236, 255, 0.14)",
    shadowColor: "#84ECFF",
    shadowOpacity: 0.34,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 0 },
  },
  buttonPressed: {
    transform: [{ scale: 0.97 }],
    opacity: 0.92,
  },
  buttonListening: {
    borderColor: "rgba(132, 236, 255, 0.52)",
    backgroundColor: "#101A2B",
    shadowOpacity: 0.28,
    shadowRadius: 24,
  },
});
