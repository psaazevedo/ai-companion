import { useEffect, useMemo, useRef, type CSSProperties, type MouseEvent as ReactMouseEvent } from "react";

import { useAgentStore } from "@/stores/agentStore";

type OrbProps = {
  isListening: boolean;
  isSpeaking: boolean;
  isThinking: boolean;
  variant?: "hero" | "compact";
  modeProgress?: number;
  insightOpen?: boolean;
};

type OrbMode =
  | "idle"
  | "listening"
  | "thinking"
  | "speaking"
  | "interrupting"
  | "dormant";

type SurfacePoint = {
  lat: number;
  lon: number;
  latJitter: number;
  lonJitter: number;
  size: number;
  noiseA: number;
  noiseB: number;
  lift: number;
  scatter: number;
};

type SprayPoint = {
  angle: number;
  distance: number;
  size: number;
  noise: number;
  drift: number;
};

type OrbConfig = {
  radiusScale: number;
  spin: number;
  turbulence: number;
  shellWave: number;
  spray: number;
  glow: number;
  audioResponse: number;
  swirl: number;
};

const SURFACE_POINTS = createSurfacePoints(34, 54);
const SPRAY_POINTS = createSprayPoints(260);

const PALETTE = {
  cyan: [132, 236, 255] as const,
  blue: [66, 124, 255] as const,
  violet: [126, 93, 255] as const,
  pink: [255, 88, 222] as const,
  orange: [255, 132, 74] as const,
  white: [255, 248, 255] as const,
};

const MODE_CONFIG: Record<OrbMode, OrbConfig> = {
  idle: {
    radiusScale: 0.865,
    spin: 0.16,
    turbulence: 0.038,
    shellWave: 0.03,
    spray: 0.18,
    glow: 0.62,
    audioResponse: 0,
    swirl: 0.02,
  },
  listening: {
    radiusScale: 0.872,
    spin: 0.18,
    turbulence: 0.046,
    shellWave: 0.04,
    spray: 0.21,
    glow: 0.72,
    audioResponse: 0.24,
    swirl: 0.035,
  },
  thinking: {
    radiusScale: 0.848,
    spin: 0.11,
    turbulence: 0.1,
    shellWave: 0.075,
    spray: 0.24,
    glow: 0.76,
    audioResponse: 0,
    swirl: 0.18,
  },
  speaking: {
    radiusScale: 0.892,
    spin: 0.19,
    turbulence: 0.058,
    shellWave: 0.1,
    spray: 0.28,
    glow: 0.9,
    audioResponse: 0,
    swirl: 0.08,
  },
  interrupting: {
    radiusScale: 0.81,
    spin: 0.32,
    turbulence: 0.09,
    shellWave: 0.09,
    spray: 0.26,
    glow: 0.52,
    audioResponse: 0.06,
    swirl: 0.13,
  },
  dormant: {
    radiusScale: 0.83,
    spin: 0.07,
    turbulence: 0.024,
    shellWave: 0.018,
    spray: 0.1,
    glow: 0.32,
    audioResponse: 0,
    swirl: 0.01,
  },
};

export function Orb({
  isListening,
  isSpeaking,
  isThinking,
  variant = "hero",
  modeProgress = variant === "compact" ? 1 : 0,
  insightOpen = false,
}: OrbProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const frameRef = useRef<number>(0);
  const renderStateRef = useRef({
    mode: "idle" as OrbMode,
    targetInput: 0,
    smoothedInput: 0,
    modeProgress,
    targetInsight: insightOpen ? 1 : 0,
    smoothedInsight: 0,
    targetHover: 0,
    smoothedHover: 0,
    targetMouseX: 0.5,
    targetMouseY: 0.5,
    smoothedMouseX: 0.5,
    smoothedMouseY: 0.5,
  });

  const conversationState = useAgentStore((state) => state.conversationState);
  const orbInputLevel = useAgentStore((state) => state.orbInputLevel);

  const mode = useMemo<OrbMode>(() => {
    if (conversationState === "interrupting") {
      return "interrupting";
    }

    if (conversationState === "reconnecting" || conversationState === "error") {
      return "dormant";
    }

    if (isListening) {
      return "listening";
    }

    if (isSpeaking) {
      return "speaking";
    }

    if (isThinking) {
      return "thinking";
    }

    return "idle";
  }, [conversationState, isListening, isSpeaking, isThinking]);

  useEffect(() => {
    renderStateRef.current.mode = mode;
  }, [mode]);

  useEffect(() => {
    renderStateRef.current.targetInput = orbInputLevel;
  }, [orbInputLevel]);

  useEffect(() => {
    renderStateRef.current.modeProgress = modeProgress;
  }, [modeProgress]);

  useEffect(() => {
    renderStateRef.current.targetInsight = insightOpen ? 1 : 0;
  }, [insightOpen]);

  const stageSize = useMemo(() => {
    return 560;
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }

    const context = canvas.getContext("2d");
    if (!context) {
      return;
    }

    const startedAt = performance.now();
    const sizeState = { width: 0, height: 0, dpr: 1 };

    const tick = (now: number) => {
      const elapsed = (now - startedAt) / 1000;
      const bounds = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);

      const nextWidth = Math.max(1, Math.round(bounds.width * dpr));
      const nextHeight = Math.max(1, Math.round(bounds.height * dpr));
      if (
        nextWidth !== sizeState.width ||
        nextHeight !== sizeState.height ||
        dpr !== sizeState.dpr
      ) {
        sizeState.width = nextWidth;
        sizeState.height = nextHeight;
        sizeState.dpr = dpr;
        canvas.width = nextWidth;
        canvas.height = nextHeight;
      }

      drawParticleOrb(context, sizeState.width, sizeState.height, elapsed, renderStateRef.current);
      frameRef.current = window.requestAnimationFrame(tick);
    };

    frameRef.current = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frameRef.current);
  }, []);

  return (
    <div style={shellStyle}>
      <div
        onMouseEnter={(event) => {
          updatePointerPosition(event, renderStateRef.current);
          renderStateRef.current.targetHover = 1;
        }}
        onMouseMove={(event) => updatePointerPosition(event, renderStateRef.current)}
        onMouseLeave={() => {
          renderStateRef.current.targetHover = 0;
        }}
        style={{
          ...stageStyle,
          width: `${stageSize}px`,
          height: `${stageSize}px`,
        }}
      >
        <canvas ref={canvasRef} style={canvasStyle} aria-hidden="true" />
      </div>
    </div>
  );
}

const shellStyle: CSSProperties = {
  width: "100%",
  display: "flex",
  justifyContent: "center",
  alignItems: "center",
};

const stageStyle: CSSProperties = {
  maxWidth: "76vw",
  maxHeight: "76vw",
  aspectRatio: "1 / 1",
  display: "flex",
  justifyContent: "center",
  alignItems: "center",
  cursor: "default",
};

const canvasStyle: CSSProperties = {
  width: "100%",
  height: "100%",
  display: "block",
  overflow: "visible",
};

function updatePointerPosition(
  event: ReactMouseEvent<HTMLDivElement>,
  state: { targetMouseX: number; targetMouseY: number }
) {
  const bounds = event.currentTarget.getBoundingClientRect();
  state.targetMouseX = clamp((event.clientX - bounds.left) / Math.max(bounds.width, 1), 0, 1);
  state.targetMouseY = clamp((event.clientY - bounds.top) / Math.max(bounds.height, 1), 0, 1);
}

function drawParticleOrb(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  elapsed: number,
  state: {
    mode: OrbMode;
    targetInput: number;
    smoothedInput: number;
    modeProgress: number;
    targetInsight: number;
    smoothedInsight: number;
    targetHover: number;
    smoothedHover: number;
    targetMouseX: number;
    targetMouseY: number;
    smoothedMouseX: number;
    smoothedMouseY: number;
  }
) {
  const config = MODE_CONFIG[state.mode];
  const compactness = smoothstep(clamp(state.modeProgress, 0, 1));
  const surfacePoints = SURFACE_POINTS;
  const sprayPoints = SPRAY_POINTS;
  state.smoothedInput = lerp(state.smoothedInput, state.targetInput, 0.16);
  state.smoothedInsight = lerp(state.smoothedInsight, state.targetInsight, 0.045);
  state.smoothedHover = lerp(state.smoothedHover, state.targetHover, 0.075);
  state.smoothedMouseX = lerp(state.smoothedMouseX, state.targetMouseX, 0.14);
  state.smoothedMouseY = lerp(state.smoothedMouseY, state.targetMouseY, 0.14);
  const insightOpen = state.smoothedInsight * (1 - compactness);
  const hoverEnergy = state.smoothedHover * (1 - compactness);

  ctx.clearRect(0, 0, width, height);
  ctx.save();
  ctx.scale(1, 1);
  ctx.globalCompositeOperation = "screen";

  const centerX = width / 2;
  const centerY = height / 2;
  const pointerX = state.smoothedMouseX * width;
  const pointerY = state.smoothedMouseY * height;
  const sphereRadius =
    Math.min(width, height) * lerp(0.34, 0.31, compactness) * (1 + hoverEnergy * 0.025);

  drawAmbientGlow(
    ctx,
    centerX,
    centerY,
    sphereRadius,
    config,
    elapsed,
    state.smoothedInput,
    compactness,
    hoverEnergy
  );
  drawSpray(
    ctx,
    centerX,
    centerY,
    sphereRadius,
    config,
    elapsed,
    state.smoothedInput,
    compactness,
    hoverEnergy,
    sprayPoints
  );

  const pulse =
    state.mode === "speaking"
      ? 0.5 + 0.5 * Math.sin(elapsed * 7.4)
      : state.mode === "thinking"
        ? 0.5 + 0.5 * Math.sin(elapsed * 2.1)
        : 0.5 + 0.5 * Math.sin(elapsed * 1.5);

  const rotY = elapsed * config.spin + state.smoothedInput * 0.35;
  const rotX = Math.sin(elapsed * 0.45) * 0.16 + (state.mode === "thinking" ? 0.12 : 0.05);
  const perspective = sphereRadius * 3.1;

  const projected = surfacePoints.map((point) => {
    const coreBreakup = Math.pow(Math.max(0, Math.cos(point.lat)), 1.35) * (1 - compactness * 0.38);
    const organicLat =
      point.lat
      + point.latJitter * (0.75 + hoverEnergy * 0.35)
      + Math.sin(elapsed * 0.42 + point.noiseA * 1.7) * 0.011 * coreBreakup;
    const organicLon =
      point.lon
      + point.lonJitter * (0.75 + hoverEnergy * 0.35)
      + Math.cos(elapsed * 0.38 + point.noiseB * 1.45) * 0.017 * coreBreakup;
    const noise =
      Math.sin(point.noiseA + elapsed * (0.78 + config.spin * 1.8) + organicLat * 3.4) * 0.55
      + Math.cos(point.noiseB - elapsed * (0.66 + config.spin * 1.4) + organicLon * 2.3) * 0.45;

    let radialScale = config.radiusScale + noise * config.turbulence;
    radialScale += Math.sin(elapsed * 1.6 + point.lift * 5.8) * 0.012;
    radialScale += Math.sin(elapsed * 0.7 + point.noiseA + point.noiseB) * 0.014 * coreBreakup * point.scatter;
    radialScale += hoverEnergy * (0.012 + (0.5 + 0.5 * Math.sin(point.noiseA + elapsed * 2.2)) * 0.018);

    if (state.mode === "listening") {
      const ripple =
        Math.sin(elapsed * 11.2 - organicLat * 5.2 + organicLon * 2.4 + point.noiseA) * 0.5 + 0.5;
      radialScale += state.smoothedInput * config.audioResponse * (0.35 + ripple * 0.65);
    } else if (state.mode === "speaking") {
      const wave =
        Math.sin(elapsed * 8.5 - organicLat * 7.8 + organicLon * 1.6 + point.noiseB) * 0.5 + 0.5;
      radialScale += wave * config.shellWave * (0.3 + pulse * 0.7);
    } else if (state.mode === "thinking") {
      const swirlWave =
        Math.sin(elapsed * 3.4 + organicLon * 3.2 - organicLat * 9.4 + point.noiseA) * 0.5 + 0.5;
      radialScale += (swirlWave - 0.5) * config.shellWave;
    } else if (state.mode === "interrupting") {
      radialScale -= 0.04;
      radialScale += Math.sin(elapsed * 13.5 + point.noiseA * 2.1) * 0.026;
    }

    let x = Math.cos(organicLat) * Math.cos(organicLon);
    let y = Math.sin(organicLat);
    let z = Math.cos(organicLat) * Math.sin(organicLon);

    x *= radialScale;
    y *= radialScale;
    z *= radialScale;

    if (state.mode === "thinking" || state.mode === "interrupting") {
      const swirlAmount = config.swirl * (0.4 + 0.6 * (0.5 + 0.5 * Math.sin(elapsed * 2.2 + point.noiseB)));
      const twist = swirlAmount * Math.sin(organicLat * 4.8 + elapsed * 2.8);
      const cosTwist = Math.cos(twist);
      const sinTwist = Math.sin(twist);
      const nextX = x * cosTwist - z * sinTwist;
      const nextZ = x * sinTwist + z * cosTwist;
      x = nextX;
      z = nextZ;
      y *= state.mode === "thinking" ? 0.92 : 0.88;
    }

    const rotatedY = y * Math.cos(rotX) - z * Math.sin(rotX);
    const rotatedZ = y * Math.sin(rotX) + z * Math.cos(rotX);
    const rotatedX = x * Math.cos(rotY) + rotatedZ * Math.sin(rotY);
    const finalZ = -x * Math.sin(rotY) + rotatedZ * Math.cos(rotY);

    const depth = (finalZ + 1.3) / 2.3;
    const projection = perspective / (perspective - finalZ * sphereRadius * 0.7);
    let screenX = centerX + rotatedX * sphereRadius * projection;
    let screenY = centerY - rotatedY * sphereRadius * projection;
    const centerScatter = coreBreakup * (0.58 + point.scatter * 0.84);
    const scatterRadius = sphereRadius * lerp(0.014, 0.004, compactness) * centerScatter;
    screenX += Math.sin(point.noiseA * 1.9 + elapsed * 0.52) * scatterRadius;
    screenY += Math.cos(point.noiseB * 1.6 + elapsed * 0.48) * scatterRadius;

    let baseColor = getPointColor(rotatedX, rotatedY, depth);
    const edge = 1 - Math.abs(finalZ);
    const heroAlpha = clamp(0.16 + depth * 0.62 + edge * 0.12 + config.glow * 0.05, 0.14, 0.94);
    const compactAlpha = clamp(0.08 + depth * 0.36 + edge * 0.08 + config.glow * 0.03, 0.07, 0.64);
    let alpha = lerp(heroAlpha, compactAlpha, compactness) * (1 + hoverEnergy * 0.22);
    const heroRadius = (0.8 + point.size * 1.35 + depth * 1.65) * projection;
    const compactRadius = (0.18 + point.size * 0.42 + depth * 0.62) * projection;
    let radius =
      lerp(heroRadius, compactRadius, compactness)
      * (1 + hoverEnergy * 0.16)
      * (0.9 + point.scatter * 0.22);

    if (hoverEnergy > 0.01) {
      const pointerDx = screenX - pointerX;
      const pointerDy = screenY - pointerY;
      const pointerDistance = Math.sqrt(pointerDx * pointerDx + pointerDy * pointerDy);
      const touchRadius = sphereRadius * 0.46;
      const localTouch = Math.pow(clamp(1 - pointerDistance / touchRadius, 0, 1), 2.2) * hoverEnergy;

      if (localTouch > 0.001) {
        const safeDistance = Math.max(pointerDistance, 1);
        const pushX = pointerDx / safeDistance;
        const pushY = pointerDy / safeDistance;
        const tangentX = -pushY;
        const tangentY = pushX;
        const shimmer = Math.sin(elapsed * 13.2 + point.noiseA * 2.1 + point.noiseB) * 0.5 + 0.5;
        const localPulse = sphereRadius * localTouch * (0.035 + point.scatter * 0.026);

        screenX += pushX * localPulse + tangentX * localPulse * 0.42 * shimmer;
        screenY += pushY * localPulse + tangentY * localPulse * 0.42 * (1 - shimmer);
        radius *= 1 + localTouch * (0.82 + point.scatter * 0.52);
        alpha *= 1 + localTouch * 0.48;
        baseColor = mixColors(baseColor, PALETTE.white, localTouch * 0.32);
      }
    }

    if (insightOpen > 0.01) {
      const gapWidth = sphereRadius * 1.62;
      const gapHeight = sphereRadius * 0.32;
      const dx = (screenX - centerX) / gapWidth;
      const dy = (screenY - centerY) / gapHeight;
      const openingInfluence = clamp(1 - (dx * dx + dy * dy), 0, 1) * insightOpen;
      const splitDirection = screenY >= centerY ? 1 : -1;
      screenY += splitDirection * openingInfluence * sphereRadius * 0.22;
      alpha *= 1 - openingInfluence * 0.72;
      radius *= 1 - openingInfluence * 0.24;
    }

    return { alpha, color: baseColor, radius, screenX, screenY, z: finalZ };
  });

  projected.sort((left, right) => left.z - right.z);

  for (const point of projected) {
    ctx.beginPath();
    ctx.fillStyle = rgba(point.color, point.alpha);
    ctx.arc(point.screenX, point.screenY, point.radius, 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.restore();
}

function drawAmbientGlow(
  ctx: CanvasRenderingContext2D,
  centerX: number,
  centerY: number,
  sphereRadius: number,
  config: OrbConfig,
  elapsed: number,
  inputLevel: number,
  compactness: number,
  hoverEnergy: number
) {
  const energy = (config.glow + inputLevel * 0.26 + hoverEnergy * 0.22) * lerp(1, 0.52, compactness);
  const topGlow = ctx.createRadialGradient(
    centerX - sphereRadius * 0.34,
    centerY - sphereRadius * 0.42,
    sphereRadius * 0.08,
    centerX - sphereRadius * 0.34,
    centerY - sphereRadius * 0.42,
    sphereRadius * 1.08
  );
  topGlow.addColorStop(0, rgba(PALETTE.cyan, 0.28 * energy));
  topGlow.addColorStop(1, "rgba(0,0,0,0)");

  const sideGlow = ctx.createRadialGradient(
    centerX + sphereRadius * 0.38,
    centerY + sphereRadius * 0.06,
    sphereRadius * 0.1,
    centerX + sphereRadius * 0.38,
    centerY + sphereRadius * 0.06,
    sphereRadius * 1.15
  );
  sideGlow.addColorStop(0, rgba(PALETTE.pink, 0.24 * energy));
  sideGlow.addColorStop(1, "rgba(0,0,0,0)");

  const lowerGlow = ctx.createRadialGradient(
    centerX,
    centerY + sphereRadius * 0.6 + Math.sin(elapsed * 2.4) * sphereRadius * 0.04,
    sphereRadius * 0.08,
    centerX,
    centerY + sphereRadius * 0.6,
    sphereRadius * 1.05
  );
  lowerGlow.addColorStop(0, rgba(PALETTE.orange, 0.16 * energy));
  lowerGlow.addColorStop(1, "rgba(0,0,0,0)");

  ctx.fillStyle = topGlow;
  ctx.fillRect(0, 0, centerX * 2, centerY * 2);
  ctx.fillStyle = sideGlow;
  ctx.fillRect(0, 0, centerX * 2, centerY * 2);
  ctx.fillStyle = lowerGlow;
  ctx.fillRect(0, 0, centerX * 2, centerY * 2);
}

function drawSpray(
  ctx: CanvasRenderingContext2D,
  centerX: number,
  centerY: number,
  sphereRadius: number,
  config: OrbConfig,
  elapsed: number,
  inputLevel: number,
  compactness: number,
  hoverEnergy: number,
  sprayPoints: SprayPoint[]
) {
  const pulse = config.shellWave * sphereRadius * (0.55 + inputLevel * 1.15 + hoverEnergy * 0.45);

  for (const particle of sprayPoints) {
    const orbit = particle.distance + Math.sin(elapsed * 0.9 + particle.drift) * sphereRadius * 0.02;
    const spread =
      sphereRadius
      * config.spray
      * (0.14 + particle.noise * 0.22 + inputLevel * 0.18 + hoverEnergy * 0.16)
      * (0.5 + 0.5 * Math.sin(elapsed * (2.2 + particle.noise) + particle.angle * 2.6));
    const x =
      centerX
      + Math.cos(particle.angle) * (sphereRadius + orbit + spread)
      + Math.sin(elapsed * 1.4 + particle.drift) * pulse * 0.16;
    const y =
      centerY
      + Math.sin(particle.angle) * (sphereRadius + orbit + spread)
      + Math.cos(elapsed * 1.2 + particle.drift) * pulse * 0.14;
    const edgeColor = mixColors(
      mixColors(PALETTE.cyan, PALETTE.pink, clamp(0.5 + Math.cos(particle.angle) * 0.42, 0, 1)),
      PALETTE.orange,
      clamp(Math.sin(particle.angle) * 0.5 + 0.5, 0, 1) * 0.44
    );

    ctx.beginPath();
    ctx.fillStyle = rgba(
      edgeColor,
      lerp(
        0.1 + particle.noise * 0.34 + config.glow * 0.06,
        0.03 + particle.noise * 0.12 + config.glow * 0.03,
        compactness
      ) * (1 + hoverEnergy * 0.42)
    );
    ctx.arc(
      x,
      y,
      particle.size
        * lerp(0.7 + config.spray, 0.34 + config.spray * 0.44, compactness),
      0,
      Math.PI * 2
    );
    ctx.fill();
  }
}

function getPointColor(x: number, y: number, depth: number) {
  let color = mixColors(PALETTE.blue, PALETTE.pink, clamp(0.46 + x * 0.42 - y * 0.08, 0, 1));
  color = mixColors(color, PALETTE.cyan, clamp(0.55 + y * 0.75, 0, 1) * 0.66);
  color = mixColors(color, PALETTE.orange, clamp(-y - 0.12, 0, 1) * 0.72);
  color = mixColors(color, PALETTE.white, clamp(depth - 0.72, 0, 1) * 0.28);
  return color;
}

function createSurfacePoints(rows: number, columns: number) {
  const points: SurfacePoint[] = [];

  for (let row = 0; row < rows; row += 1) {
    const v = row / (rows - 1);
    const lat = (v - 0.5) * Math.PI;
    const ringStrength = Math.max(0.18, Math.cos(lat));
    const ringColumns = Math.max(16, Math.round(columns * (0.46 + ringStrength * 0.74)));
    const offset = row % 2 === 0 ? 0 : Math.PI / ringColumns;

    for (let column = 0; column < ringColumns; column += 1) {
      const lon = (column / ringColumns) * Math.PI * 2 + offset;
      const sizeSeed = seededNoise((row + 1) * 17.11 + (column + 1) * 3.7);

      points.push({
        lat,
        lon,
        latJitter: (seededNoise((row + 1) * 14.47 + (column + 1) * 9.81) - 0.5) * 0.07 * ringStrength,
        lonJitter: (seededNoise((row + 1) * 5.91 + (column + 1) * 11.23) - 0.5) * 0.1 * ringStrength,
        size: 0.55 + sizeSeed * 1.1,
        noiseA: seededNoise((row + 1) * 9.13 + (column + 1) * 4.22) * Math.PI * 2,
        noiseB: seededNoise((row + 1) * 6.41 + (column + 1) * 7.35) * Math.PI * 2,
        lift: seededNoise((row + 1) * 12.7 + (column + 1) * 5.18),
        scatter: seededNoise((row + 1) * 15.73 + (column + 1) * 2.94),
      });
    }
  }

  return points;
}

function createSprayPoints(count: number) {
  const points: SprayPoint[] = [];

  for (let index = 0; index < count; index += 1) {
    const noise = seededNoise((index + 1) * 8.97);
    points.push({
      angle: seededNoise((index + 1) * 3.11) * Math.PI * 2,
      distance: 14 + seededNoise((index + 1) * 5.37) * 54,
      size: noise > 0.9 ? 2.5 : noise > 0.62 ? 1.6 : 0.9,
      noise,
      drift: seededNoise((index + 1) * 13.5) * Math.PI * 2,
    });
  }

  return points;
}

function seededNoise(seed: number) {
  const value = Math.sin(seed * 43758.5453123 + 0.9182) * 43758.5453123;
  return value - Math.floor(value);
}

function mixColors(a: readonly number[], b: readonly number[], amount: number) {
  const t = clamp(amount, 0, 1);
  return [
    Math.round(lerp(a[0], b[0], t)),
    Math.round(lerp(a[1], b[1], t)),
    Math.round(lerp(a[2], b[2], t)),
  ] as const;
}

function rgba(color: readonly number[], alpha: number) {
  return `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${clamp(alpha, 0, 1).toFixed(3)})`;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function lerp(from: number, to: number, amount: number) {
  return from + (to - from) * amount;
}

function smoothstep(value: number) {
  const t = clamp(value, 0, 1);
  return t * t * (3 - 2 * t);
}
