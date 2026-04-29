# Codex Instructions

This repository has an active product design system:

- `TOKENS.md` contains raw colors, spacing, radius, type, motion, and fixed dimensions.
- `DESIGN.md` explains how those values should be used.
- `COMPONENTS.md` records reusable component patterns and variants.

When working on any user-facing UI, UX, copy, motion, interaction, or visual change, read those files first in this order:

1. `TOKENS.md`
2. `DESIGN.md`
3. `COMPONENTS.md`

Treat them as active product guidance, not optional reference material.

For design-facing work:

- Preserve the companion's voice-first, orb-led, memory-transparent product identity.
- Reuse existing component patterns before creating new ones.
- Prefer named components over large inline UI blocks. Screens should mostly orchestrate state, data, animation values, and layout composition.
- Extract UI into a component when it has its own visual states, accessibility labels, styles, repeated structure, or design-system identity.
- Prefer calm, useful, honest interface choices over decorative or trend-driven choices.
- Keep one clear primary action per surface.
- Use concise, specific, front-loaded copy.
- Make system state, memory confidence, evidence, and recovery paths visible when relevant.
- Avoid adding visual effects, panels, cards, or explanations unless they improve usability, trust, clarity, or continuity.
- Use token values from `TOKENS.md` for new colors, spacing, radius, type, and motion unless a specific fixed-format element requires an exception.
- Check new UI against the review checklist in `DESIGN.md` before considering the work complete.

If a new reusable component or variant is created, update `COMPONENTS.md` in the same change.

If a user asks for a design change that conflicts with `DESIGN.md`, call out the tradeoff briefly and choose the path that best serves the product unless the user explicitly directs otherwise.

## graphify

This project is configured for a graphify knowledge graph at graphify-out/.

Rules:
- If graphify-out/GRAPH_REPORT.md exists, read it before answering architecture or codebase questions
- If graphify-out/wiki/index.md exists, navigate it before reading raw files
- After modifying code files in this session, run `graphify update .` to keep the graph current (AST-only, no API cost)
