import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

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
  onClose,
}: MemoryInspectorProps) {
  const { snapshot, isLoading, error, refresh } = useMemoryAtlas(userId, visible);
  const [tab, setTab] = useState<AtlasTab>("map");
  const [selectedNodeId, setSelectedNodeId] = useState<string>("user");

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

  const selectedNode =
    visibleNodes.find((node) => node.id === selectedNodeId) ?? visibleNodes[0] ?? null;
  const evidence = selectedNode ? snapshot?.evidence[selectedNode.id] ?? [] : [];

  if (!visible) {
    return null;
  }

  return (
    <View style={styles.panel}>
      <View style={styles.header}>
        <View style={styles.headerCopy}>
          <Text style={styles.eyebrow}>Memory Atlas</Text>
          <Text style={styles.title}>How the companion currently understands you</Text>
          <Text style={styles.subtitle}>
            Distilled concepts, learned response patterns, and the episodes that shaped them.
          </Text>
        </View>
        <View style={styles.headerActions}>
          <Pressable onPress={() => void refresh()} style={styles.headerButton}>
            <Text style={styles.headerButtonLabel}>Refresh</Text>
          </Pressable>
          <Pressable onPress={onClose} style={[styles.headerButton, styles.headerButtonGhost]}>
            <Text style={styles.headerButtonLabel}>Close</Text>
          </Pressable>
        </View>
      </View>

      <View style={styles.summaryRow}>
        {renderSummaryChip("Episodes", snapshot?.summary.episodes ?? 0)}
        {renderSummaryChip("Semantic", snapshot?.summary.semantic ?? 0)}
        {renderSummaryChip("Procedural", snapshot?.summary.procedural ?? 0)}
        {renderSummaryChip("Active", snapshot?.summary.status_counts.active ?? 0)}
        {renderSummaryChip("Archived", snapshot?.summary.status_counts.archived ?? 0)}
      </View>

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
            <>
              <View style={styles.mapCard}>
                <AtlasMap
                  nodes={layoutNodes}
                  edges={snapshot.map.edges}
                  selectedNodeId={selectedNode?.id ?? "user"}
                  onSelect={setSelectedNodeId}
                />
              </View>

              {selectedNode ? (
                <View style={styles.detailCard}>
                  <View style={styles.detailHeader}>
                    <View>
                      <Text style={styles.detailEyebrow}>
                        {selectedNode.layer === "core"
                          ? "Core Node"
                          : `${titleCase(selectedNode.layer)} Memory`}
                      </Text>
                      <Text style={styles.detailTitle}>{selectedNode.label}</Text>
                    </View>
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
                    {renderMetric("Recalled", String(selectedNode.recall_count))}
                  </View>

                  {selectedNode.archive_reason ? (
                    <Text style={styles.archiveNote}>
                      Archived because it was {selectedNode.archive_reason.replace("_", " ")}.
                    </Text>
                  ) : null}

                  <View style={styles.section}>
                    <Text style={styles.sectionTitle}>Why the system believes this</Text>
                    {evidence.length ? (
                      evidence.map((episode) => (
                        <View key={episode.id} style={styles.evidenceCard}>
                          <View style={styles.evidenceMeta}>
                            <Text style={styles.evidenceTone}>
                              {titleCase(episode.emotional_tone)}
                            </Text>
                            <Text style={styles.evidenceTime}>
                              {formatDate(episode.timestamp)}
                            </Text>
                          </View>
                          <Text style={styles.evidenceSummary}>{episode.summary}</Text>
                        </View>
                      ))
                    ) : (
                      <Text style={styles.emptyHint}>
                        This memory is currently distilled more from reinforcement than from one
                        explicit source episode.
                      </Text>
                    )}
                  </View>

                  {snapshot.map.relations.length ? (
                    <View style={styles.section}>
                      <Text style={styles.sectionTitle}>Nearby relationships</Text>
                      <View style={styles.relationWrap}>
                        {relatedRelations(snapshot.map.relations, selectedNode).map((relation) => (
                          <View key={relation.id} style={styles.relationChip}>
                            <Text style={styles.relationText}>
                              {relation.source_label} {relation.relation} {relation.target_label}
                            </Text>
                          </View>
                        ))}
                      </View>
                    </View>
                  ) : null}
                </View>
              ) : null}
            </>
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
    </View>
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

      <rect x="0" y="0" width="760" height="520" rx="28" fill="#0A0F1D" />
      <circle cx="380" cy="250" r="160" fill="url(#atlasCore)" />
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
              fill={isSelected ? "#F5F8FF" : "#AFC0E8"}
              fontSize="11"
              textAnchor="middle"
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

const styles = StyleSheet.create({
  panel: {
    width: 560,
    maxWidth: 620,
    minWidth: 460,
    flexShrink: 0,
    borderLeftWidth: 1,
    borderLeftColor: "rgba(143, 170, 222, 0.16)",
    backgroundColor: "#0A0F19",
    paddingHorizontal: 24,
    paddingTop: 24,
    paddingBottom: 18,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 18,
    alignItems: "flex-start",
  },
  headerCopy: {
    flex: 1,
    gap: 6,
  },
  eyebrow: {
    color: "#8AA1D4",
    fontSize: 11,
    letterSpacing: 2.8,
    textTransform: "uppercase",
    fontWeight: "700",
  },
  title: {
    color: "#F4F7FF",
    fontSize: 24,
    lineHeight: 30,
    fontWeight: "700",
  },
  subtitle: {
    color: "#9FB0D4",
    fontSize: 14,
    lineHeight: 20,
  },
  headerActions: {
    flexDirection: "row",
    gap: 10,
  },
  headerButton: {
    paddingHorizontal: 14,
    height: 38,
    borderRadius: 999,
    backgroundColor: "#111A2C",
    borderWidth: 1,
    borderColor: "rgba(146, 229, 255, 0.22)",
    justifyContent: "center",
  },
  headerButtonGhost: {
    backgroundColor: "#0C1321",
    borderColor: "rgba(146, 170, 222, 0.16)",
  },
  headerButtonLabel: {
    color: "#E8EEFC",
    fontSize: 13,
    fontWeight: "600",
  },
  summaryRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
    marginTop: 18,
  },
  summaryChip: {
    minWidth: 92,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 16,
    backgroundColor: "#101726",
    borderWidth: 1,
    borderColor: "rgba(129, 152, 201, 0.18)",
    gap: 4,
  },
  summaryLabel: {
    color: "#8AA1D4",
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 1.3,
    fontWeight: "700",
  },
  summaryValue: {
    color: "#F4F7FF",
    fontSize: 18,
    fontWeight: "700",
  },
  tabs: {
    flexDirection: "row",
    gap: 10,
    marginTop: 20,
  },
  tabButton: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 999,
    backgroundColor: "#0F1524",
    borderWidth: 1,
    borderColor: "rgba(129, 152, 201, 0.14)",
  },
  tabButtonActive: {
    backgroundColor: "rgba(117, 220, 255, 0.12)",
    borderColor: "rgba(117, 220, 255, 0.28)",
  },
  tabLabel: {
    color: "#93A8D3",
    fontSize: 13,
    fontWeight: "600",
  },
  tabLabelActive: {
    color: "#EAF7FF",
  },
  stateCard: {
    marginTop: 20,
    minHeight: 120,
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
    marginTop: 18,
  },
  scrollContent: {
    gap: 18,
    paddingBottom: 60,
  },
  mapCard: {
    borderRadius: 30,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: "rgba(129, 152, 201, 0.14)",
    backgroundColor: "#0B101D",
  },
  mapSvg: {
    width: "100%",
    aspectRatio: 1.46,
  },
  detailCard: {
    padding: 20,
    borderRadius: 26,
    backgroundColor: "#0F1626",
    borderWidth: 1,
    borderColor: "rgba(129, 152, 201, 0.14)",
    gap: 16,
  },
  detailHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 16,
  },
  detailEyebrow: {
    color: "#8BA2D5",
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 1.8,
    fontWeight: "700",
    marginBottom: 5,
  },
  detailTitle: {
    color: "#F4F7FF",
    fontSize: 24,
    lineHeight: 28,
    fontWeight: "700",
    maxWidth: 300,
  },
  statusPills: {
    alignItems: "flex-end",
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
    color: "#DAE4FA",
    fontSize: 15,
    lineHeight: 22,
  },
  metricsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
  },
  metricCard: {
    minWidth: 108,
    paddingHorizontal: 12,
    paddingVertical: 12,
    borderRadius: 16,
    backgroundColor: "#10192B",
    borderWidth: 1,
    borderColor: "rgba(129, 152, 201, 0.12)",
    gap: 4,
  },
  metricLabel: {
    color: "#8AA1D4",
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 1.1,
    fontWeight: "700",
  },
  metricValue: {
    color: "#F4F7FF",
    fontSize: 18,
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
    color: "#F4F7FF",
    fontSize: 16,
    fontWeight: "700",
  },
  evidenceCard: {
    padding: 14,
    borderRadius: 16,
    backgroundColor: "#10192A",
    borderWidth: 1,
    borderColor: "rgba(129, 152, 201, 0.12)",
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
    color: "#D2DCF2",
    fontSize: 14,
    lineHeight: 20,
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
    gap: 14,
  },
  timelineCard: {
    padding: 18,
    borderRadius: 22,
    backgroundColor: "#0F1626",
    borderWidth: 1,
    borderColor: "rgba(129, 152, 201, 0.12)",
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
    gap: 18,
  },
  patternCard: {
    padding: 16,
    borderRadius: 18,
    backgroundColor: "#0F1626",
    borderWidth: 1,
    borderColor: "rgba(129, 152, 201, 0.12)",
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
