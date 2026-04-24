import { MessageCircle, Mic } from "lucide-react-native";
import { Pressable, StyleSheet, View } from "react-native";

type ModeToggleProps = {
  mode: "voice" | "chat";
  onChange: (mode: "voice" | "chat") => void;
};

export function ModeToggle({ mode, onChange }: ModeToggleProps) {
  return (
    <View style={styles.track}>
      <Pressable
        accessibilityLabel="Voice mode"
        onPress={() => onChange("voice")}
        style={[styles.option, mode === "voice" ? styles.optionActive : null]}
      >
        <Mic
          size={20}
          color={mode === "voice" ? "#08101D" : "#AFC2E6"}
          strokeWidth={2.2}
        />
      </Pressable>
      <Pressable
        accessibilityLabel="Chat mode"
        onPress={() => onChange("chat")}
        style={[styles.option, mode === "chat" ? styles.optionActive : null]}
      >
        <MessageCircle
          size={20}
          color={mode === "chat" ? "#08101D" : "#AFC2E6"}
          strokeWidth={2.2}
        />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  track: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    padding: 5,
    borderRadius: 999,
    backgroundColor: "rgba(9, 15, 27, 0.78)",
    borderWidth: 1,
    borderColor: "rgba(145, 190, 255, 0.14)",
  },
  option: {
    width: 48,
    height: 40,
    borderRadius: 999,
    alignItems: "center",
    justifyContent: "center",
  },
  optionActive: {
    backgroundColor: "#EAF4FF",
    shadowColor: "#84ECFF",
    shadowOpacity: 0.22,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 0 },
  },
});
