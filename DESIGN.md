# Design Guidelines

Universal design rules for this AI companion. Raw token values live in `TOKENS.md`. Reusable component patterns live in `COMPONENTS.md`.

This product is voice-first, memory-rich, emotionally present, and inspectable. The interface should feel like one continuous relationship rather than a pile of screens. Design decisions should protect that feeling while making the system easier to understand, trust, and control.

## How Codex Should Use This File

For any user-facing UI, UX, copy, motion, interaction, or visual change, read in this order:

1. `TOKENS.md` - raw colors, spacing, radius, type, and motion values.
2. `DESIGN.md` - rules for how those values are used.
3. `COMPONENTS.md` - existing component patterns and reuse expectations.
4. The task prompt - what to build now.

Use this prompt structure for design-facing work:

1. Experience intent - what should the user feel or understand?
2. Product context - voice, chat, memory, proactive insight, or settings.
3. Existing pattern - which component or surface this extends.
4. Global rules - spacing, color, type, motion, accessibility.
5. Negative constraints - what must not happen.
6. Component spec - states, transitions, edge cases, data states.

Reuse before creating. If a component pattern exists in `COMPONENTS.md`, use it. If the need is close, extend that pattern and update `COMPONENTS.md`. Create a new pattern only when it is genuinely new.

## North Star

The companion should feel calm, intelligent, and alive without becoming theatrical. It should make complex memory and conversation systems feel understandable through clear state, restrained surfaces, useful motion, and specific language.

Prefer:

- Presence over decoration.
- Clarity over mystery.
- Trust over spectacle.
- Continuity over isolated screens.
- User control over hidden intelligence.

Avoid:

- Marketing-page patterns inside the product experience.
- Decorative effects that do not communicate state, relationship, memory, or focus.
- Multiple competing calls to action.
- Generic AI copy that could belong to any assistant.
- Interfaces that imply certainty, intimacy, urgency, or capability the system has not earned.

## Current Product Language

### Product Shape

- The orb is the primary presence surface. It represents attention, listening, thinking, speaking, interruption, dormancy, and emotional energy.
- Voice mode is the default posture: minimal, centered, and low-friction.
- Chat mode is a deeper written surface, not a separate product. It should feel like the same relationship becoming more precise.
- The Memory Atlas is the transparency surface for the companion's mind. It should explain what the system remembers, why it believes something, how strong a memory is, and where it came from.
- Proactive insight should be rare and high-value. The UI should treat it as "worth saying", not as a notification feed.

### Visual Tone

- Base canvas: very dark blue-black, centered around `#080B14`.
- Primary light: cool cyan and soft blue for presence, listening, memory, and active system state.
- Secondary light: violet/pink for user-side input and relational contrast.
- Warm accent: amber/orange only for thinking, salience, caution, or transition.
- Text: near-white for primary content, muted blue-gray for secondary text.
- Surfaces: translucent, layered, and quiet. Use borders and shadow as separation tools, not ornament.

### Spatial Language

- Keep the main experience centered and uncluttered.
- Preserve a strong figure-ground relationship between the active task and the canvas.
- Group related controls tightly: microphone and mode switch belong together; Memory Atlas controls belong together; memory details belong with evidence and metrics.
- Use large empty areas intentionally around the orb and conversation focus. Empty space is part of the calm.
- Avoid card-on-card layouts. Use cards for repeated items, flyouts, modals, or evidence blocks, not for every page section.

## Motion

Motion should express state, attention, continuity, or response. It should not exist only because the screen can animate.

### Curves

| Situation | Curve | Use for |
|---|---|---|
| Entering element | `Easing.out(Easing.cubic)` or `cubic-bezier(0.22, 1, 0.36, 1)` | Element appears or settles |
| Exiting element | `Easing.in(Easing.cubic)` or `cubic-bezier(0.55, 0, 1, 0.45)` | Element leaves |
| Mode transition | `Easing.inOut(Easing.cubic)` | Voice/chat or panel transformation |
| Idle loop | `Easing.inOut(Easing.sin)` or `ease-in-out` | Breathing, pulsing, ambient presence |
| Weighted return | Spring with stiffness near `120-150`, damping near `18-24` | Focused cards, active lens items |

Do not use generic "smooth" as a spec. Name duration and easing.

### Durations

| Element type | Duration | Notes |
|---|---:|---|
| Hover, press, focus | `80-150ms` | Instant feel |
| Small appear/fade | `180-250ms` | Single element |
| Flyout or modal | `240-360ms` | Panel-level |
| Atlas open/close | `420-520ms` | Large overlay |
| Voice/chat mode shift | `620-720ms` | Major identity-preserving transition |
| Proactive insight reveal | `900-1100ms` | Rare, ambient arrival |
| Orb idle cycle | `3-8s` | Alive but not distracting |

Exits should usually be 60-80% of the matching enter duration.

### Stagger

- When multiple elements enter together, delay each by `30-60ms`.
- Cap item-by-item stagger at 5 items.
- Beyond 5 items, stagger groups instead of every element.

### Continuous Animation

For orbs, pulses, breathing effects:

- Cycle: `3-8s`.
- Scale amplitude: `2-6%`.
- Opacity amplitude: no more than `0.15-0.22`.
- Pause or quiet down during direct user interaction when possible.
- Continuous motion must communicate presence or state, not decoration.

### Performance

- Prefer animating `transform` and `opacity`.
- Avoid animating `height`, `width`, `left`, `top`, `margin`, or layout-affecting values.
- Use stable dimensions for fixed-format elements so motion does not cause layout shift.

## Gestalt And Layout

### Proximity

Related elements should be spatially grouped.

- Internal gap: `4-12px`.
- Between related controls: `12-24px`.
- Between groups: `24-48px`.
- Between major sections: `48-80px`.

Do not use borders or backgrounds to group what spacing already groups.

### Similarity

Elements with similar meaning should share visual treatment. If two elements look the same, they should behave the same. Never use similar styling for different functionality.

### Continuity

Layouts should guide the eye in a smooth, predictable path. Maintain a clear central axis in voice mode and a stable vertical rhythm in chat and Atlas surfaces.

### Figure / Ground

Important content must stand apart clearly from the background. Use contrast, scale, spacing, and placement before adding decoration.

Minimum contrast:

- Text: `4.5:1` where practical.
- UI elements and focus indicators: `3:1`.

### Closure

Related content should feel visually complete. Use cards or flyouts only when content is a distinct object, inspection surface, modal, or repeated record.

### Common Fate

Elements moving together are perceived as a unit. Synchronize motion for grouped controls and stagger only when revealing separate items.

## Space Over Boxes

Space is the default container. A box is justified only when content is a distinct object or needs functional elevation.

Use a container for:

- Message or conversation object.
- Evidence, memory, or timeline record.
- Modal, flyout, overlay, or composer.
- Interactive control cluster.
- Alert, error, or proactive insight.

Avoid a container for:

- Text-only page sections.
- Small label/value groups that spacing can handle.
- Decorative grouping.
- Every section on a screen.
- A card inside another card.

When separation is needed, prefer:

- More whitespace.
- Stronger type hierarchy.
- Shared alignment.
- Subtle background tone shift.
- A single hairline separator as a last resort.

## Typography And Copy

### Type Scale

Use the current React Native/system stack unless a deliberate brand typography decision is made. Do not introduce a new font family casually.

| Role | Size | Weight | Line height | Use |
|---|---:|---:|---:|---|
| Display | `28-40` | `700-800` | `1.1-1.2` | Atlas headers, rare hero-like moments |
| H1/H2 | `22-28` | `600-800` | `1.15-1.25` | Surface titles |
| H3 | `18-20` | `600-700` | `1.25-1.35` | Section titles, empty states |
| Body | `14-16` | `400-500` | `1.45-1.65` | Readable content |
| Dense body | `12-14` | `400-600` | `1.35-1.5` | Metadata-heavy surfaces |
| Caption/label | `11-13` | `500-700` | `1.25-1.4` | Labels, chips, helper text |
| Eyebrow | `10-12` | `700-800` | `1.2` | Sparse uppercase metadata |

### Type Rules

- Use no more than 3 primary font sizes on a single compact surface.
- Use weight and color for secondary emphasis before adding more sizes.
- Body and small text should not use negative letter spacing.
- Uppercase belongs to compact labels, not paragraphs or primary actions.
- Center-align only short, centered voice-mode content. Left-align dense reading and Atlas inspection.
- Keep body line length roughly `45-75` characters where layout allows.

### Copy Rules

- Copy should be concise, specific, and front-loaded.
- Prefer plain words over brand mood.
- Do not over-explain features inside the active product surface. Put deeper explanations in inspection, help, or empty states.
- Never imply the companion knows more than the data supports.
- Avoid generic AI language such as "unlock your potential", "supercharge", "seamless", or "personalized experience" unless the surrounding sentence makes it concrete.

Good:

- "What I remember, how strongly, and why."
- "Select a memory to inspect it."
- "Distilled from repeated reinforcement rather than one clear episode."

Weak:

- "Your intelligent AI memory hub."
- "Unlock deeper insights from your personalized companion."
- "Everything you need, all in one place."

## Color And Contrast

Use color roles from `TOKENS.md`. Do not invent new color roles without updating that file.

- `bg.base` is the stable app canvas.
- `presence.cyan` and `presence.blue` communicate companion state, listening, memory, and active system status.
- `user.violet` and `user.pink` communicate user-side input or relational contrast.
- `state.thinking` communicates thinking, salience, or caution.
- `state.error` is only for actual errors.
- Text colors must stay readable on translucent dark surfaces.
- Do not rely on color alone for status. Pair color with labels, icons, shape, opacity, or placement.
- One accent should dominate a single control group. Do not make every element glow.

The orb is allowed to use glow, particles, and living light because it is the companion's presence surface. Other UI should use glow sparingly and functionally.

## Product-Specific Rules

### Voice Mode

- The orb remains the hero.
- The microphone action should be immediately available and visually distinct.
- The user should always understand whether the companion is listening, thinking, speaking, reconnecting, or idle.
- Do not place explanatory onboarding text in the center experience unless the user is blocked.
- Keep voice controls compact. Voice mode should feel ready, not busy.

### Chat Mode

- Chat mode should feel like a continuation of voice, not a separate chat app.
- Preserve the current lens-like focus: recent exchange is primary; older context recedes.
- The composer should stay obvious, stable, and reachable.
- Empty states should be short and specific.
- Avoid dense transcripts unless the user explicitly enters a history or review surface.

### Memory Atlas

- The Atlas should make memory inspectable, not merely decorative.
- Always connect memory claims to confidence, strength, status, source, or relationship when available.
- Use group color consistently: goals, projects, preferences, procedures, patterns, identity, and concepts should keep stable visual identities.
- Archived, pinned, active, outdated, and superseded memories must be visually and textually distinguishable.
- Evidence should be easy to scan before it is detailed.
- Memory UI must be honest about uncertainty. Do not make inferred beliefs feel like facts.

### Proactive Insights

- A proactive insight should earn its interruption.
- The UI should make dismissal easy and non-punitive.
- Copy should be concrete and useful, not vaguely therapeutic.
- Do not create a feed of generic insights. One strong insight beats several weak ones.

## Components And Controls

- Prefer named TSX components over large inline JSX blocks. Product screens should compose components and own orchestration, not bury full controls directly in the screen file.
- Extract a component when a UI element has independent visual states, accessibility labels, motion, substantial styles, repeated structure, or a reusable product role.
- Small one-off layout wrappers can stay inline when extraction would add indirection without reuse, state isolation, or clarity.
- Use icon buttons for familiar compact actions: microphone, send, close, refresh, atlas.
- Use text labels when the action is unfamiliar, high-stakes, destructive, or benefits from explicit wording.
- Use segmented controls for mutually exclusive modes.
- Use tabs for alternate views within a single surface.
- Use chips for compact metadata, statuses, counts, and categories.
- Use flyouts for focused inspection when the user needs context without leaving the current surface.
- Primary action should have one dominant treatment. Secondary actions should be visually quieter.
- Keep touch targets at least `44x44px` where possible.
- Controls must have accessible labels when the visible UI is icon-only.

## Interaction Cost

- Common tasks should require minimal movement: speak, switch to chat, send, open Atlas, close Atlas.
- Make recovery obvious: close, dismiss, retry, refresh, undo, or back out.
- Do not add confirmation steps to low-risk actions.
- Add friction for destructive, privacy-sensitive, or hard-to-reverse memory actions.
- Prefer visible controls over hidden gestures for important behavior.

## Tradeoffs

- Clarity over minimalism when the task is unfamiliar, high-stakes, privacy-sensitive, or related to memory correction.
- Safety over speed when an action deletes, archives, pins, unpins, shares, or overwrites user memory.
- Familiarity over novelty when the user needs to act quickly or repeatedly.
- Simplicity over feature exposure when a surface feels overloaded. Use progressive disclosure.
- Specificity over brand flair when copy is vague.
- Calm over excitement when the interface is presenting system intelligence.
- Trust over persuasion in memory, identity, mental-state, or personal-history surfaces.

## Negative Constraints

Never:

- Add multiple equal-weight primary actions.
- Add a card or bordered wrapper around every section.
- Nest cards inside cards.
- Use glow, blur, particles, or gradients on ordinary controls without a state reason.
- Use color as the only status indicator.
- Animate layout properties when transform/opacity can do the job.
- Use continuous animations faster than a `3s` cycle.
- Use generic AI marketing copy.
- Hide important controls behind gestures.
- Show disabled controls without context when the reason is not obvious.
- Add memory claims without evidence, confidence, or qualifying language when such metadata is available.
- Make destructive or privacy-sensitive memory actions look casual.

## Transformation Playbook

- Multiple equal-weight CTAs: choose one primary action and demote the rest.
- Cluttered screen: remove low-value sections, reduce repeated content, and increase spacing between groups.
- Messy layout: strengthen alignment, unify spacing, and normalize component treatments.
- Generic copy: rewrite the headline and support text to be concrete and front-loaded.
- Hard form: reduce field count, stack fields in one column, put labels above inputs, and replace dropdowns when a better control exists.
- Trendy but weak style: remove decorative effects that reduce contrast, hierarchy, or durability.
- Disconnected information: tighten grouping and establish clearer container logic.
- Lost primary content: increase contrast, scale, spacing, or placement around the primary message/action.
- Destructive action too easy: reduce prominence, separate placement, and add confirmation or undo.
- Memory claim too confident: add source, confidence, status, or qualifying language.

## Design Review Checklist

Before shipping a UI change, ask:

- What user task or understanding does this change improve?
- Is there one clear primary action?
- Are related elements grouped and unrelated elements separated?
- Is system state visible when relevant?
- Is the copy specific, concise, and honest?
- Does the design lower interaction cost or cognitive load?
- Are similar elements visually and behaviorally consistent?
- Does the UI work without relying on color alone?
- Are touch targets, contrast, focus, and labels accessible?
- Does motion communicate state, attention, continuity, or response?
- Does the change reuse or extend existing component patterns?
- Does the change preserve the companion's calm, voice-first, memory-transparent identity?

If the answer to any of these is weak, revise before adding more design.
