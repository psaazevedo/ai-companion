# Component Patterns

Reusable UI patterns for the AI companion. Check this file before creating new UI. Reuse, then extend, then create.

## Reuse Protocol

1. Check whether a matching pattern exists here.
2. Reuse the existing component or visual behavior when possible.
3. If a variant is needed, extend the existing pattern and update this file.
4. Create a new pattern only for genuinely new behavior or information architecture.
5. New patterns must use `TOKENS.md` and follow `DESIGN.md`.

## Componentization Rule

Prefer a named TSX component over inline screen markup when the UI has:

- Its own visual states.
- Accessibility labels or interaction semantics.
- Motion or animated transitions.
- Substantial styles.
- Repeated structure.
- A design-system role worth documenting here.

Keep screen files focused on orchestration: state, hooks, data flow, animation values, and high-level composition. Small one-off layout wrappers may stay inline when extracting them would not improve reuse or clarity.

## Orb Presence

Source:

- `frontend/components/Orb.web.tsx`
- `frontend/components/Orb.tsx`

Purpose:

- Primary companion presence.
- Communicates idle, listening, thinking, speaking, interrupting, and dormant states.

Rules:

- The orb is allowed to be more expressive than ordinary UI.
- Color and motion must map to state.
- Do not reuse orb glow/particle treatment on unrelated controls.
- Keep voice mode centered around the orb unless the user is in a deeper surface.

Known variants:

- `hero` for primary voice mode.
- `compact` for reduced/transitioned contexts.

## Voice Action Button

Source:

- `frontend/components/VoiceActionButton.tsx`

Purpose:

- Primary voice interaction: hold to speak.

Rules:

- Must remain visually distinct from the mode toggle.
- Must expose `accessibilityLabel`.
- Listening state should be visibly different through color, border, glow, and pulse.
- Do not add a second primary action beside it in voice mode.

## Mode Toggle

Source:

- `frontend/components/ModeToggle.tsx`

Purpose:

- Switches between voice and chat.

Rules:

- Use segmented control behavior for mutually exclusive app modes.
- Use icon-only options when icons are familiar and labels are accessible.
- Active state uses a light fill and inverse icon color.
- Do not create alternate voice/chat switchers.

## Conversation Lens

Source:

- `frontend/components/ConversationSheet.tsx`

Purpose:

- Focused chat mode that treats text conversation as the same memory stream as voice.

Rules:

- Recent exchange is primary; older exchanges may recede.
- Composer remains stable and reachable.
- Streaming, pending, loading, and error states must be clear.
- Avoid turning this into a generic dense transcript unless creating a dedicated history surface.

Key dimensions:

- Lens item height: `300`.
- Input min/max: `50/156`.
- Composer shell min height: `76`.

## Composer

Source:

- `frontend/components/ConversationSheet.tsx`

Purpose:

- Text input and send action.

Rules:

- Send is icon-only with disabled state.
- Placeholder should be short and state-aware.
- Input should expand within a controlled max height.
- User must understand why sending is unavailable when the reason is not obvious.

## Memory Atlas Overlay

Source:

- `frontend/components/MemoryInspector.web.tsx`

Purpose:

- Inspectable model of what the companion remembers, how strongly, and why.

Rules:

- Memory claims should connect to status, confidence, strength, source, or relationship.
- Tabs are appropriate for map, timeline, and patterns.
- Color by memory group must stay stable.
- Archived/pinned/active states must be visually and textually distinguishable.
- Use flyouts for focused inspection without leaving the map.

## Atlas Toggle

Source:

- `frontend/components/AtlasToggle.tsx`

Purpose:

- Opens/closes Memory Atlas.

Rules:

- Floating circular icon button.
- Uses user/close icon swap.
- Must expose an accessibility label that changes with state.
- Should not compete with the primary voice action.

## Notification / Proactive Insight

Source:

- `frontend/components/Notification.tsx`

Purpose:

- Presents rare proactive insights.

Rules:

- Use only for content that is genuinely worth interrupting the main experience.
- Dismissal should be easy and non-punitive.
- Copy must be concrete and useful.
- Do not turn this into a generic notification feed.

## Tabs

Source:

- `frontend/components/MemoryInspector.web.tsx`

Purpose:

- Switch between sibling views within the same surface.

Rules:

- Use for map/timeline/pattern-style alternates.
- Active state should be obvious through fill and text color.
- Do not use tabs for primary app modes; use the mode toggle pattern.

## Chips And Pills

Source:

- `frontend/components/MemoryInspector.web.tsx`
- `frontend/components/Notification.tsx`

Purpose:

- Compact metadata, counts, statuses, categories, and dismiss actions.

Rules:

- Keep labels short.
- Use status text in addition to color.
- Use pill radius only for small metadata/control elements.

## Evidence Cards

Source:

- `frontend/components/MemoryInspector.web.tsx`

Purpose:

- Display sources for memory claims.

Rules:

- Evidence is a distinct record, so a card is appropriate.
- Include metadata first, then summary.
- Keep summaries short and scannable.
- Do not present evidence as more certain than the source supports.
