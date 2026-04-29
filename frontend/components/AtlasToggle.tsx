import { UserRound, X } from "lucide-react-native";
import { Animated, Pressable, StyleSheet, View } from "react-native";

type AtlasToggleProps = {
  isOpen: boolean;
  progress: Animated.Value;
  onToggle: () => void;
};

export function AtlasToggle({ isOpen, progress, onToggle }: AtlasToggleProps) {
  const atlasIconOpacity = progress.interpolate({
    inputRange: [0, 0.42, 1],
    outputRange: [1, 0, 0],
  });

  const atlasCloseOpacity = progress.interpolate({
    inputRange: [0, 0.48, 1],
    outputRange: [0, 0, 1],
  });

  const atlasIconRotate = progress.interpolate({
    inputRange: [0, 1],
    outputRange: ["0deg", "-90deg"],
  });

  const atlasCloseRotate = progress.interpolate({
    inputRange: [0, 1],
    outputRange: ["90deg", "0deg"],
  });

  return (
    <View pointerEvents="box-none" style={styles.dock}>
      <Pressable
        onPress={onToggle}
        accessibilityRole="button"
        accessibilityLabel={isOpen ? "Close memory atlas" : "Open memory atlas"}
        hitSlop={10}
        style={[
          styles.button,
          isOpen ? styles.buttonOpen : null,
          { outlineStyle: "none", outlineWidth: 0 } as never,
        ]}
      >
        <Animated.View
          pointerEvents="none"
          style={[
            styles.iconLayer,
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
            styles.iconLayer,
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
  );
}

const styles = StyleSheet.create({
  dock: {
    position: "absolute",
    top: 22,
    right: 24,
    zIndex: 120,
  },
  button: {
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
  buttonOpen: {
    backgroundColor: "rgba(20, 30, 49, 0.92)",
    borderColor: "rgba(244,248,255,0.28)",
  },
  iconLayer: {
    position: "absolute",
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    alignItems: "center",
    justifyContent: "center",
  },
});
