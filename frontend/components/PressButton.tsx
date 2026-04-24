import { Pressable, StyleSheet, Text } from "react-native";

type PressButtonProps = {
  onPressIn: () => void;
  onPressOut: () => void;
  label?: string;
};

export function PressButton({ onPressIn, onPressOut, label = "Hold To Talk" }: PressButtonProps) {
  return (
    <Pressable
      onPressIn={onPressIn}
      onPressOut={onPressOut}
      style={({ pressed }) => [styles.button, pressed && styles.buttonPressed]}
    >
      <Text style={styles.label}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    minHeight: 58,
    minWidth: 220,
    paddingHorizontal: 28,
    borderRadius: 999,
    backgroundColor: "#0F1726",
    borderWidth: 1,
    borderColor: "rgba(186,208,255,0.22)",
    justifyContent: "center",
    alignItems: "center",
    shadowColor: "#65BFFF",
    shadowOpacity: 0.14,
    shadowRadius: 22,
    shadowOffset: { width: 0, height: 0 },
  },
  buttonPressed: {
    transform: [{ scale: 0.98 }],
    opacity: 0.92,
  },
  label: {
    color: "#EAF1FF",
    fontSize: 14,
    fontWeight: "700",
    letterSpacing: 1.6,
    textTransform: "uppercase",
  },
});
