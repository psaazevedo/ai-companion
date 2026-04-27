import { useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Animated,
  Easing,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { RefreshCw, X } from "lucide-react-native";

import {
  type AtlasEdge,
  type AtlasNode,
  type AtlasRelation,
  type AtlasTimelineEntry,
  useMemoryAtlas,
} from "@/hooks/useMemoryAtlas";

type MemoryInspectorProps = {
  userId: string;
  visible: boolean;
  onClose: () => void;
  progress?: Animated.Value;
};

type AtlasTab = "map" | "timeline" | "patterns";

type PositionedNode = AtlasNode & {
  x: number;
  y: number;
  radius: number;
  color: string;
};

const GROUP_ORDER = [
  "goal",
  "project",
  "preference",
  "procedure",
  "pattern",
  "identity",
  "concept",
];

const GROUP_ANGLES: Record<string, number> = {
  goal: -90,
  project: -28,
  preference: 34,
  procedure: 132,
  pattern: 205,
  identity: 255,
  concept: 305,
};

const GROUP_COLORS: Record<string, string> = {
  core: "#F1F5FF",
  goal: "#7FDBFF",
  project: "#66A6FF",
  preference: "#E36BFF",
  procedure: "#7AF2C3",
  pattern: "#FFB36B",
  identity: "#FFD86B",
  concept: "#9FA8FF",
};

export function MemoryInspector({
  userId,
  visible,
  progress,
}: MemoryInspectorProps) {
  const { snapshot, isLoading, error, refresh } = useMemoryAtlas(userId, visible);
  const [tab, setTab] = useState<AtlasTab>("map");
  const [selectedNodeId, setSelectedNodeId] = useState<string>("user");
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const flyoutProgress = useRef(new Animated.Value(0)).current;

  const visibleNodes = useMemo(() => {
    if (!snapshot) {
      return [];
    }

    return [...snapshot.map.nodes]
      .sort((left, right) => {
        const statusRank = rankStatus(left.status) - rankStatus(right.status);
        if (statusRank !== 0) {
          return statusRank;
        }
        return right.strength - left.strength;
      })
      .slice(0, 12);
  }, [snapshot]);

  const layoutNodes = useMemo(
    () => buildAtlasLayout(visibleNodes, snapshot?.map.edges ?? []),
    [visibleNodes, snapshot]
  );

  useEffect(() => {
    if (!visible) {
      return;
    }

    const preferredNode =
      visibleNodes.find((node) => node.id === selectedNodeId) ??
      visibleNodes.find((node) => node.layer !== "core" && node.status !== "archived") ??
      visibleNodes[0];

    if (preferredNode && preferredNode.id !== selectedNodeId) {
      setSelectedNodeId(preferredNode.id);
    }
  }, [selectedNodeId, visible, visibleNodes]);

  useEffect(() => {
    if (!visible || tab !== "map") {
      setInspectorOpen(false);
    }
  }, [tab, visible]);

  useEffect(() => {
    Animated.timing(flyoutProgress, {
      toValue: inspectorOpen ? 1 : 0,
      duration: inspectorOpen ? 360 : 240,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: true,
    }).start();
  }, [flyoutProgress, inspectorOpen]);

  const selectedNode =
    visibleNodes.find((node) => node.id === selectedNodeId) ?? visibleNodes[0] ?? null;
  const evidence = selectedNode ? snapshot?.evidence[selectedNode.id] ?? [] : [];
  const handleSelectNode = (nodeId: string) => {
    setSelectedNodeId(nodeId);
    if (nodeId !== "user") {
      setInspectorOpen(true);
    }
  };
  const flyoutStyle = {
    opacity: flyoutProgress,
    transform: [
      {
        translateX: flyoutProgress.interpolate({
          inputRange: [0, 1],
          outputRange: [34, 0],
        }),
      },
    ],
  };

  if (!visible) {
    return null;
  }

  const entranceStyle = progress
    ? {
        opacity: progress,
        transform: [
          {
            scale: progress.interpolate({
              inputRange: [0, 1],
              outputRange: [0.985, 1],
            }),
          },
        ],
      }
    : null;

  return (
    <Animated.View style={[styles.panel, entranceStyle]}>
      <View style={styles.header}>
        <View style={styles.headerCopy}>
          <Text style={styles.eyebrow}>Atlas</Text>
          <Text style={styles.subtitle}>What I remember, how strongly, and why.</Text>
        </View>
        <View style={styles.headerActions}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Refresh memory atlas"
            onPress={() => void refresh()}
            style={styles.headerButton}
          >
            <RefreshCw size={16} color="#DFF8FF" strokeWidth={2} />
          </Pressable>
        </View>
      </View>

      <View style={styles.controlRail}>
        <View style={styles.tabs}>
          {(["map", "timeline", "patterns"] as AtlasTab[]).map((tabOption) => (
            <Pressable
              key={tabOption}
              onPress={() => setTab(tabOption)}
              style={[styles.tabButton, tab === tabOption && styles.tabButtonActive]}
            >
              <Text style={[styles.tabLabel, tab === tabOption && styles.tabLabelActive]}>
                {titleCase(tabOption)}
              </Text>
            </Pressable>
          ))}
        </View>

        <View style={styles.summaryRow}>
          {renderSummaryChip("episodes", snapshot?.summary.episodes ?? 0)}
          {renderSummaryChip("beliefs", snapshot?.summary.semantic ?? 0)}
          {renderSummaryChip("procedures", snapshot?.summary.procedural ?? 0)}
          {renderSummaryChip("active", snapshot?.summary.status_counts.active ?? 0)}
        </View>
      </View>

      {isLoading ? (
        <View style={styles.stateCard}>
          <ActivityIndicator color="#8DE1FF" />
          <Text style={styles.stateText}>Loading memory atlas…</Text>
        </View>
      ) : null}

      {!isLoading && error ? (
        <View style={styles.stateCard}>
          <Text style={styles.stateText}>{error}</Text>
        </View>
      ) : null}

      {!isLoading && !error && snapshot ? (
        <ScrollView
          style={styles.scroll}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          {tab === "map" ? (
            <View style={styles.mapWorkspace}>
              <View style={styles.mapStage}>
                <AtlasMap
                  nodes={layoutNodes}
                  edges={snapshot.map.edges}
                  selectedNodeId={selectedNode?.id ?? "user"}
                  onSelect={handleSelectNode}
                />
                {!inspectorOpen ? (
                  <View pointerEvents="none" style={styles.mapHint}>
                    <Text style={styles.mapHintText}>Select a memory to inspect it</Text>
                  </View>
                ) : null}
              </View>

              {selectedNode && selectedNode.id !== "user" ? (
                <Animated.View
                  pointerEvents={inspectorOpen ? "auto" : "none"}
                  style={[
                    styles.detailFlyout,
                    flyoutStyle,
                  ]}
                >
                  <View style={styles.detailHeader}>
                    <View style={styles.detailTitleWrap}>
                      <Text style={styles.detailEyebrow}>
                        {selectedNode.layer === "core"
                          ? "Center"
                          : titleCase(selectedNode.layer)}
                      </Text>
                      <Text style={styles.detailTitle}>{selectedNode.label}</Text>
                    </View>
                    <Pressable
                      accessibilityRole="button"
                      accessibilityLabel="Close memory details"
                      onPress={() => setInspectorOpen(false)}
                      style={styles.detailClose}
                    >
                      <X size={16} color="#DCEBFF" strokeWidth={2.1} />
                    </Pressable>
                    <View style={styles.statusPills}>
                      <Text style={[styles.statusPill, statusStyle(selectedNode.status)]}>
                        {titleCase(selectedNode.status)}
                      </Text>
                      <Text
                        style={[
                          styles.statusPill,
                          {
                            color: colorForGroup(selectedNode.group),
                            borderColor: withAlpha(colorForGroup(selectedNode.group), 0.35),
                            backgroundColor: withAlpha(colorForGroup(selectedNode.group), 0.12),
                          },
                        ]}
                      >
                        {titleCase(selectedNode.group)}
                      </Text>
                    </View>
                  </View>

                  <Text style={styles.detailBody}>{selectedNode.content}</Text>

                  <View style={styles.metricsRow}>
                    {renderMetric("Strength", `${Math.round(selectedNode.strength * 100)}%`)}
                    {renderMetric("Confidence", `${Math.round(selectedNode.confidence * 100)}%`)}
                    {renderMetric("Reinforced", String(selectedNode.reinforcement_count))}
                  </View>

                  {selectedNode.archive_reason ? (
                    <Text style={styles.archiveNote}>
                      Archived because it was {selectedNode.archive_reason.replace("_", " ")}.
                    </Text>
                  ) : null}

                  <View style={styles.section}>
                    <Text style={styles.sectionTitle}>Sources</Text>
                    {evidence.length ? (
                      evidence.slice(0, 2).map((episode) => (
                        <View key={episode.id} style={styles.evidenceCard}>
                          <View style={styles.evidenceMeta}>
                            <Text style={styles.evidenceTone}>
                              {titleCase(episode.emotional_tone)}
                            </Text>
                            <Text style={styles.evidenceTime}>
                              {formatDate(episode.timestamp)}
                            </Text>
                          </View>
                          <Text style={styles.evidenceSummary} numberOfLines={3}>
                            {cleanEvidenceSummary(episode.summary)}
                          </Text>
                        </View>
                      ))
                    ) : (
                      <Text style={styles.emptyHint}>
                        Distilled from repeated reinforcement rather than one clear episode.
                      </Text>
                    )}
                  </View>

                  {snapshot.map.relations.length ? (
                    <View style={styles.section}>
                      <Text style={styles.sectionTitle}>Connected to</Text>
                      <View style={styles.relationWrap}>
                        {relatedRelations(snapshot.map.relations, selectedNode)
                          .slice(0, 5)
                          .map((relation) => (
                            <View key={relation.id} style={styles.relationChip}>
                              <Text style={styles.relationText}>
                                {relation.source_label} {relation.relation} {relation.target_label}
                              </Text>
                            </View>
                          ))}
                      </View>
                    </View>
                  ) : null}
                </Animated.View>
              ) : null}
            </View>
          ) : null}

          {tab === "timeline" ? (
            <View style={styles.timelineStack}>
              {snapshot.timeline.map((entry) => (
                <View key={entry.id} style={styles.timelineCard}>
                  <View style={styles.timelineHeader}>
                    <Text style={styles.timelineTitle}>{entry.title}</Text>
                    <Text style={styles.timelineDate}>{formatDate(entry.timestamp)}</Text>
                  </View>
                  <View style={styles.timelineMeta}>
                    <Text style={styles.timelineTone}>{titleCase(entry.emotional_tone)}</Text>
                    <Text style={styles.timelineSalience}>
                      Salience {Math.round(entry.salience * 100)}%
                    </Text>
                    <Text style={styles.timelineSalience}>
                      {titleCase(entry.memory_status)}
                    </Text>
                  </View>
                  <Text style={styles.timelineSummary}>{entry.summary}</Text>
                </View>
              ))}
            </View>
          ) : null}

          {tab === "patterns" ? (
            <View style={styles.patternStack}>
              <PatternSection
                title="Distilled Semantic Memory"
                nodes={visibleNodes.filter((node) => node.layer === "semantic")}
                selectedNodeId={selectedNodeId}
                onSelect={setSelectedNodeId}
              />
              <PatternSection
                title="Learned Response Procedures"
                nodes={visibleNodes.filter((node) => node.layer === "procedural")}
                selectedNodeId={selectedNodeId}
                onSelect={setSelectedNodeId}
              />
            </View>
          ) : null}
        </ScrollView>
      ) : null}
    </Animated.View>
  );
}

function PatternSection({
  title,
  nodes,
  selectedNodeId,
  onSelect,
}: {
  title: string;
  nodes: AtlasNode[];
  selectedNodeId: string;
  onSelect: (nodeId: string) => void;
}) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {nodes.length ? (
        nodes.map((node) => {
          const selected = node.id === selectedNodeId;
          return (
            <Pressable
              key={node.id}
              onPress={() => onSelect(node.id)}
              style={[
                styles.patternCard,
                selected && {
                  borderColor: withAlpha(colorForGroup(node.group), 0.45),
                  backgroundColor: withAlpha(colorForGroup(node.group), 0.12),
                },
              ]}
            >
              <View style={styles.patternHeader}>
                <Text style={styles.patternTitle}>{node.label}</Text>
                <Text style={styles.patternStrength}>
                  {Math.round(node.strength * 100)}%
                </Text>
              </View>
              <Text style={styles.patternBody}>{node.content}</Text>
            </Pressable>
          );
        })
      ) : (
        <Text style={styles.emptyHint}>No patterns distilled yet.</Text>
      )}
    </View>
  );
}

function AtlasMap({
  nodes,
  edges,
  selectedNodeId,
  onSelect,
}: {
  nodes: PositionedNode[];
  edges: AtlasEdge[];
  selectedNodeId: string;
  onSelect: (nodeId: string) => void;
}) {
  const centerNode = nodes.find((node) => node.id === "user");
  const orbitNodes = nodes.filter((node) => node.id !== "user");

  return (
    <svg viewBox="0 0 760 520" style={styles.mapSvg as never}>
      <defs>
        <radialGradient id="atlasCore" cx="50%" cy="48%" r="56%">
          <stop offset="0%" stopColor="rgba(134,235,255,0.22)" />
          <stop offset="40%" stopColor="rgba(134,235,255,0.08)" />
          <stop offset="100%" stopColor="rgba(5,10,21,0)" />
        </radialGradient>
        <linearGradient id="atlasGlow" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="rgba(117,220,255,0.42)" />
          <stop offset="100%" stopColor="rgba(218,84,255,0.32)" />
        </linearGradient>
      </defs>

      <rect x="0" y="0" width="760" height="520" rx="28" fill="transparent" />
      <circle cx="380" cy="250" r="168" fill="url(#atlasCore)" />
      <circle
        cx="380"
        cy="250"
        r="178"
        fill="none"
        stroke="rgba(146,170,222,0.08)"
        strokeWidth="1"
      />
      <circle
        cx="380"
        cy="250"
        r="218"
        fill="none"
        stroke="url(#atlasGlow)"
        strokeOpacity="0.12"
        strokeWidth="1"
      />

      {edges.map((edge) => {
        const source = nodes.find((node) => node.id === edge.source);
        const target = nodes.find((node) => node.id === edge.target);
        if (!source || !target) {
          return null;
        }

        return (
          <line
            key={edge.id}
            x1={source.x}
            y1={source.y}
            x2={target.x}
            y2={target.y}
            stroke={withAlpha(target.color, edge.weight > 0.9 ? 0.52 : 0.28)}
            strokeWidth={edge.weight > 0.95 ? 2.4 : 1.4}
          />
        );
      })}

      {orbitNodes.map((node) => {
        const isSelected = node.id === selectedNodeId;
        return (
          <g
            key={node.id}
            onClick={() => onSelect(node.id)}
            style={{ cursor: "pointer" }}
          >
            <circle
              cx={node.x}
              cy={node.y}
              r={node.radius + 15}
              fill={withAlpha(node.color, node.status === "archived" ? 0.05 : 0.12)}
            />
            <circle
              cx={node.x}
              cy={node.y}
              r={node.radius}
              fill={withAlpha(node.color, node.status === "archived" ? 0.12 : 0.18)}
              stroke={isSelected ? "#EFF5FF" : withAlpha(node.color, 0.72)}
              strokeWidth={isSelected ? 2.4 : 1.4}
            />
            <circle
              cx={node.x}
              cy={node.y}
              r={Math.max(10, node.radius - 8)}
              fill="#0B1020"
              opacity={node.status === "archived" ? 0.75 : 0.92}
            />
            <text
              x={node.x}
              y={node.y + 4}
              fill="#F5F8FF"
              fontSize="10"
              textAnchor="middle"
              style={{ letterSpacing: 0.4 }}
            >
              {shortLabel(node.label)}
            </text>
            <text
              x={node.x}
              y={node.y + node.radius + 18}
              fill="#F5F8FF"
              fontSize="11"
              textAnchor="middle"
              opacity={isSelected ? 1 : 0}
            >
              {node.label}
            </text>
          </g>
        );
      })}

      {centerNode ? (
        <g>
          <circle cx={centerNode.x} cy={centerNode.y} r="52" fill="rgba(241,245,255,0.08)" />
          <circle cx={centerNode.x} cy={centerNode.y} r="38" fill="rgba(241,245,255,0.12)" />
          <circle
            cx={centerNode.x}
            cy={centerNode.y}
            r="26"
            fill="#09101F"
            stroke="#F3F6FF"
            strokeOpacity="0.78"
            strokeWidth="1.4"
          />
          <text
            x={centerNode.x}
            y={centerNode.y + 5}
            fill="#F5F8FF"
            fontSize="13"
            textAnchor="middle"
            style={{ letterSpacing: 1.1 }}
          >
            YOU
          </text>
        </g>
      ) : null}
    </svg>
  );
}

function buildAtlasLayout(nodes: AtlasNode[], edges: AtlasEdge[]): PositionedNode[] {
  const width = 760;
  const height = 520;
  const centerX = width / 2;
  const centerY = height / 2 - 10;

  const sortedNodes = [...nodes].sort((left, right) => {
    if (left.id === "user") {
      return -1;
    }
    if (right.id === "user") {
      return 1;
    }
    const groupRank = GROUP_ORDER.indexOf(left.group) - GROUP_ORDER.indexOf(right.group);
    if (groupRank !== 0) {
      return groupRank;
    }
    return right.strength - left.strength;
  });

  const grouped = new Map<string, AtlasNode[]>();
  for (const node of sortedNodes) {
    if (node.id === "user") {
      continue;
    }
    const group = node.group in GROUP_ANGLES ? node.group : "concept";
    grouped.set(group, [...(grouped.get(group) ?? []), node]);
  }

  const laidOut: PositionedNode[] = [];
  const userNode = sortedNodes.find((node) => node.id === "user");
  if (userNode) {
    laidOut.push({
      ...userNode,
      x: centerX,
      y: centerY,
      radius: 26,
      color: GROUP_COLORS.core,
    });
  }

  for (const group of GROUP_ORDER) {
    const groupNodes = grouped.get(group) ?? [];
    groupNodes.forEach((node, index) => {
      const count = groupNodes.length;
      const spread = count > 1 ? 36 : 0;
      const offset = count > 1 ? ((index / (count - 1)) * spread) - spread / 2 : 0;
      const angleDegrees = GROUP_ANGLES[group] + offset;
      const angle = (angleDegrees * Math.PI) / 180;
      const radiusBase = group === "goal" ? 148 : group === "procedure" ? 178 : 164;
      const radius = radiusBase + (index % 2) * 18 + (node.status === "archived" ? 18 : 0);
      laidOut.push({
        ...node,
        x: centerX + Math.cos(angle) * radius,
        y: centerY + Math.sin(angle) * (radius * 0.78),
        radius: 18 + Math.round(node.strength * 10),
        color: colorForGroup(group),
      });
    });
  }

  const connectedTargets = new Set(edges.map((edge) => edge.target));
  return laidOut.filter((node) => node.id === "user" || connectedTargets.has(node.id));
}

function relatedRelations(relations: AtlasRelation[], node: AtlasNode) {
  const normalized = node.label.toLowerCase();
  return relations.filter(
    (relation) =>
      relation.source_label.toLowerCase().includes(normalized) ||
      relation.target_label.toLowerCase().includes(normalized)
  );
}

function renderSummaryChip(label: string, value: number) {
  return (
    <View key={label} style={styles.summaryChip}>
      <Text style={styles.summaryLabel}>{label}</Text>
      <Text style={styles.summaryValue}>{value}</Text>
    </View>
  );
}

function renderMetric(label: string, value: string) {
  return (
    <View key={label} style={styles.metricCard}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={styles.metricValue}>{value}</Text>
    </View>
  );
}

function rankStatus(status: string) {
  if (status === "pinned") {
    return 0;
  }
  if (status === "active") {
    return 1;
  }
  return 2;
}

function colorForGroup(group: string) {
  return GROUP_COLORS[group] ?? GROUP_COLORS.concept;
}

function statusStyle(status: string) {
  const base =
    status === "pinned"
      ? GROUP_COLORS.identity
      : status === "archived"
        ? "#8F9BB4"
        : "#92E5FF";

  return {
    color: base,
    borderColor: withAlpha(base, 0.32),
    backgroundColor: withAlpha(base, 0.12),
  };
}

function titleCase(value: string) {
  return value
    .split(/[\s_-]+/)
    .filter(Boolean)
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join(" ");
}

function withAlpha(hex: string, alpha: number) {
  const clean = hex.replace("#", "");
  if (clean.length !== 6) {
    return hex;
  }
  const red = parseInt(clean.slice(0, 2), 16);
  const green = parseInt(clean.slice(2, 4), 16);
  const blue = parseInt(clean.slice(4, 6), 16);
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

function shortLabel(label: string) {
  const words = label.split(/\s+/).filter(Boolean);
  if (words.length === 1) {
    return words[0].slice(0, 3).toUpperCase();
  }
  return words
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? "")
    .join("");
}

function formatDate(value: string | null) {
  if (!value) {
    return "Unknown";
  }
  const date = new Date(value);
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function cleanEvidenceSummary(value: string) {
  return value
    .replace(/^User said:\s*/i, "")
    .replace(/\s*Agent replied:.*$/i, "")
    .trim();
}

const styles = StyleSheet.create({
  panel: {
    position: "absolute",
    inset: 0,
    zIndex: 70,
    backgroundColor: "rgba(8, 11, 20, 0.985)",
    paddingHorizontal: 42,
    paddingTop: 78,
    paddingBottom: 22,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 18,
    alignItems: "flex-start",
    width: "100%",
    maxWidth: 1240,
    alignSelf: "center",
  },
  headerCopy: {
    flex: 1,
    gap: 5,
  },
  eyebrow: {
    color: "#F4F8FF",
    fontSize: 28,
    lineHeight: 34,
    letterSpacing: -0.8,
    textTransform: "uppercase",
    fontWeight: "800",
  },
  subtitle: {
    color: "#8FA4CC",
    fontSize: 13,
    lineHeight: 18,
  },
  headerActions: {
    flexDirection: "row",
    gap: 10,
  },
  headerButton: {
    width: 38,
    height: 38,
    borderRadius: 999,
    backgroundColor: "rgba(17, 26, 43, 0.64)",
    borderWidth: 1,
    borderColor: "rgba(146, 229, 255, 0.18)",
    justifyContent: "center",
    alignItems: "center",
  },
  controlRail: {
    width: "100%",
    maxWidth: 1240,
    alignSelf: "center",
    marginTop: 26,
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 14,
  },
  summaryRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 14,
    alignItems: "center",
  },
  summaryChip: {
    flexDirection: "row",
    alignItems: "baseline",
    gap: 5,
  },
  summaryLabel: {
    color: "#7688AE",
    fontSize: 12,
    textTransform: "lowercase",
    letterSpacing: 0.1,
    fontWeight: "600",
  },
  summaryValue: {
    color: "#F4F7FF",
    fontSize: 14,
    fontWeight: "700",
  },
  tabs: {
    flexDirection: "row",
    gap: 4,
    padding: 4,
    borderRadius: 999,
    backgroundColor: "rgba(11, 17, 31, 0.72)",
    borderWidth: 1,
    borderColor: "rgba(129, 152, 201, 0.12)",
  },
  tabButton: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: "transparent",
  },
  tabButtonActive: {
    backgroundColor: "rgba(223, 248, 255, 0.92)",
  },
  tabLabel: {
    color: "#8DA0C8",
    fontSize: 12,
    fontWeight: "700",
  },
  tabLabelActive: {
    color: "#09101D",
  },
  stateCard: {
    marginTop: 20,
    minHeight: 120,
    width: "100%",
    maxWidth: 1240,
    alignSelf: "center",
    borderRadius: 24,
    backgroundColor: "#0E1423",
    borderWidth: 1,
    borderColor: "rgba(129, 152, 201, 0.12)",
    justifyContent: "center",
    alignItems: "center",
    gap: 12,
  },
  stateText: {
    color: "#B7C6E6",
    fontSize: 14,
  },
  scroll: {
    flex: 1,
    marginTop: 20,
    width: "100%",
    maxWidth: 1240,
    alignSelf: "center",
  },
  scrollContent: {
    gap: 20,
    paddingBottom: 60,
  },
  mapWorkspace: {
    position: "relative",
    minHeight: 620,
  },
  mapStage: {
    width: "100%",
    borderRadius: 34,
    overflow: "hidden",
    backgroundColor: "rgba(10, 16, 29, 0.38)",
    shadowColor: "#7FDBFF",
    shadowOpacity: 0.08,
    shadowRadius: 34,
    shadowOffset: { width: 0, height: 0 },
  },
  mapSvg: {
    width: "100%",
    minHeight: 610,
    aspectRatio: 1.58,
  },
  mapHint: {
    position: "absolute",
    left: 24,
    bottom: 24,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 999,
    backgroundColor: "rgba(8, 13, 25, 0.58)",
    borderWidth: 1,
    borderColor: "rgba(146, 229, 255, 0.12)",
  },
  mapHintText: {
    color: "#8DA0C8",
    fontSize: 12,
    fontWeight: "600",
  },
  detailFlyout: {
    position: "absolute",
    top: 22,
    right: 22,
    bottom: 22,
    width: 390,
    padding: 20,
    borderRadius: 32,
    backgroundColor: "rgba(9, 14, 26, 0.88)",
    borderWidth: 1,
    borderColor: "rgba(146, 229, 255, 0.16)",
    gap: 18,
    shadowColor: "#84ECFF",
    shadowOpacity: 0.16,
    shadowRadius: 40,
    shadowOffset: { width: 0, height: 0 },
  },
  detailHeader: {
    gap: 14,
    paddingBottom: 18,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(146, 229, 255, 0.13)",
  },
  detailTitleWrap: {
    gap: 5,
    paddingRight: 48,
  },
  detailClose: {
    position: "absolute",
    top: 0,
    right: 0,
    width: 34,
    height: 34,
    borderRadius: 999,
    backgroundColor: "rgba(17, 26, 43, 0.72)",
    borderWidth: 1,
    borderColor: "rgba(146, 229, 255, 0.16)",
    alignItems: "center",
    justifyContent: "center",
  },
  detailEyebrow: {
    color: "#8CEBFF",
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 1.8,
    fontWeight: "700",
  },
  detailTitle: {
    color: "#F4F7FF",
    fontSize: 30,
    lineHeight: 34,
    fontWeight: "800",
    letterSpacing: -0.8,
  },
  statusPills: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  statusPill: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 999,
    borderWidth: 1,
    overflow: "hidden",
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.9,
    textTransform: "uppercase",
  },
  detailBody: {
    color: "#CFDAF3",
    fontSize: 16,
    lineHeight: 24,
  },
  metricsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
  },
  metricCard: {
    flex: 1,
    minWidth: 74,
    paddingVertical: 4,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(129, 152, 201, 0.12)",
    gap: 2,
  },
  metricLabel: {
    color: "#8195BE",
    fontSize: 10,
    textTransform: "lowercase",
    letterSpacing: 0.2,
    fontWeight: "600",
  },
  metricValue: {
    color: "#F4F7FF",
    fontSize: 20,
    fontWeight: "700",
  },
  archiveNote: {
    color: "#AAB7D4",
    fontSize: 13,
    lineHeight: 19,
  },
  section: {
    gap: 10,
  },
  sectionTitle: {
    color: "#F4F8FF",
    fontSize: 13,
    fontWeight: "700",
    letterSpacing: 0.4,
  },
  evidenceCard: {
    paddingVertical: 12,
    paddingHorizontal: 0,
    borderRadius: 0,
    backgroundColor: "transparent",
    borderTopWidth: 1,
    borderTopColor: "rgba(129, 152, 201, 0.12)",
    gap: 8,
  },
  evidenceMeta: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  evidenceTone: {
    color: "#96F0CA",
    fontSize: 12,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 1.1,
  },
  evidenceTime: {
    color: "#8BA2D5",
    fontSize: 12,
  },
  evidenceSummary: {
    color: "#B9C7E4",
    fontSize: 13,
    lineHeight: 19,
  },
  emptyHint: {
    color: "#93A5CA",
    fontSize: 13,
    lineHeight: 19,
  },
  relationWrap: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  relationChip: {
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: "#121B2D",
    borderWidth: 1,
    borderColor: "rgba(129, 152, 201, 0.12)",
  },
  relationText: {
    color: "#C6D4F1",
    fontSize: 12,
  },
  timelineStack: {
    gap: 10,
  },
  timelineCard: {
    paddingVertical: 18,
    paddingHorizontal: 4,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(129, 152, 201, 0.12)",
    backgroundColor: "transparent",
    gap: 12,
  },
  timelineHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 12,
    alignItems: "center",
  },
  timelineTitle: {
    flex: 1,
    color: "#F4F7FF",
    fontSize: 16,
    fontWeight: "700",
  },
  timelineDate: {
    color: "#8AA1D4",
    fontSize: 12,
  },
  timelineMeta: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
  },
  timelineTone: {
    color: "#9FF3CE",
    fontSize: 12,
    textTransform: "uppercase",
    letterSpacing: 1.1,
    fontWeight: "700",
  },
  timelineSalience: {
    color: "#AFC0E8",
    fontSize: 12,
  },
  timelineSummary: {
    color: "#D6E0F5",
    fontSize: 14,
    lineHeight: 20,
  },
  patternStack: {
    gap: 20,
  },
  patternCard: {
    padding: 16,
    borderRadius: 24,
    backgroundColor: "rgba(15, 22, 38, 0.62)",
    borderWidth: 1,
    borderColor: "rgba(129, 152, 201, 0.1)",
    gap: 8,
  },
  patternHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 12,
    alignItems: "center",
  },
  patternTitle: {
    flex: 1,
    color: "#F4F7FF",
    fontSize: 15,
    fontWeight: "700",
  },
  patternStrength: {
    color: "#9DE6FF",
    fontSize: 13,
    fontWeight: "700",
  },
  patternBody: {
    color: "#D1DCF2",
    fontSize: 14,
    lineHeight: 20,
  },
});
