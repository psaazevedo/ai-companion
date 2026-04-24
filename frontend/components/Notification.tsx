import { Pressable, StyleSheet, Text, View } from "react-native";

type NotificationProps = {
  title?: string;
  text: string;
  onDismiss?: () => void;
};

export function Notification({ title, text, onDismiss }: NotificationProps) {
  return (
    <View style={styles.shell}>
      <View style={styles.header}>
        <View style={styles.copy}>
          <Text style={styles.eyebrow}>Worth saying</Text>
          {title ? <Text style={styles.title}>{title}</Text> : null}
        </View>
        {onDismiss ? (
          <Pressable onPress={onDismiss} style={styles.dismissButton}>
            <Text style={styles.dismissLabel}>Not now</Text>
          </Pressable>
        ) : null}
      </View>
      <Text style={styles.text}>{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  shell: {
    width: "100%",
    maxWidth: 380,
    paddingHorizontal: 18,
    paddingVertical: 15,
    borderRadius: 26,
    backgroundColor: "rgba(7, 12, 24, 0.82)",
    borderWidth: 1,
    borderColor: "rgba(132, 236, 255, 0.22)",
    gap: 8,
    position: "relative",
    overflow: "visible",
    shadowColor: "#84ECFF",
    shadowOpacity: 0.22,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 0 },
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 12,
  },
  copy: {
    flex: 1,
    gap: 4,
  },
  eyebrow: {
    color: "#9FEAFF",
    fontSize: 10,
    letterSpacing: 1.4,
    textTransform: "uppercase",
    fontWeight: "700",
  },
  title: {
    color: "#EDF4FF",
    fontSize: 14,
    fontWeight: "700",
    lineHeight: 18,
  },
  dismissButton: {
    paddingHorizontal: 9,
    paddingVertical: 6,
    borderRadius: 999,
    backgroundColor: "rgba(13, 20, 34, 0.82)",
    borderWidth: 1,
    borderColor: "rgba(132,236,255,0.18)",
  },
  dismissLabel: {
    color: "#B9CAE9",
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 0.8,
    textTransform: "uppercase",
  },
  text: {
    color: "#D3DEF3",
    fontSize: 13,
    lineHeight: 18,
  },
});
