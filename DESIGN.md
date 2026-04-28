# Design Guidelines

This product is a personal AI companion: voice-first, memory-rich, emotionally present, and inspectable. The interface should feel like one continuous relationship rather than a pile of screens. Design decisions should protect that feeling while making the system easier to understand, trust, and control.

The current baseline is a dark, focused canvas with a living orb at the center, a compact voice/chat mode switch, an immersive conversation lens, and a Memory Atlas for transparency. Future design work should extend this language instead of replacing it.

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

## Existing Design Language

### Product Shape

- The orb is the primary presence surface. It represents attention, listening, thinking, speaking, interruption, dormancy, and emotional energy.
- Voice mode is the default posture: minimal, centered, and low-friction.
- Chat mode is a deeper written surface, not a separate product. It should feel like the same relationship becoming more precise.
- The Memory Atlas is the transparency surface for the companion's mind. It should explain what the system remembers, why it believes something, how strong a memory is, and where it came from.
- Proactive insight should be rare and high-value. The UI should treat it as "worth saying", not as a notification feed.

### Visual Tone

- Base canvas: very dark blue-black, currently centered around `#080B14`.
- Primary light: cool cyan and soft blue for presence, listening, memory, and active system state.
- Secondary light: violet/pink for user-side input and relational contrast.
- Warm accent: amber/orange only for thinking, salience, or caution. Use sparingly.
- Text: near-white for primary content, muted blue-gray for secondary text, never low-contrast haze.
- Surfaces: translucent, layered, and quiet. Use borders and shadow as separation tools, not ornament.

### Spatial Language

- Keep the main experience centered and uncluttered.
- Preserve a strong figure-ground relationship between the active task and the canvas.
- Group related controls tightly: microphone and mode switch belong together; Memory Atlas controls belong together; memory details belong with evidence and metrics.
- Use large empty areas intentionally around the orb and conversation focus. Empty space is part of the calm.
- Avoid card-on-card layouts. Use cards for repeated items, flyouts, modals, or evidence blocks, not for every page section.

### Motion

- Motion should express state, attention, continuity, or response. It should not exist only because the screen can animate.
- Orb motion may be organic and continuous, but control motion should be quick, predictable, and subtle.
- Mode transitions should preserve spatial continuity: voice should collapse into chat rather than jump to a different world.
- Loading and streaming states should show that the system is working without creating urgency.
- Respect reduced-motion needs when that setting is available.

## Design Principles

### UI Rationale

- Every design detail must have a logical reason. UI choices should improve usability, clarity, trust, or consistency.
- Prefer the option with lower usability risk. Small ambiguities compound into friction.
- Reduce clicks, effort, movement, and thinking required to complete a task.
- Remove unnecessary information, styles, and decisions.
- Use one clearly dominant primary action.
- Group related items tightly and separate unrelated items clearly.
- Similar elements should look and behave in similar ways.
- Prefer familiar patterns unless a better alternative is clearly justified.
- Use concise, plain, front-loaded text.
- Ensure sufficient contrast and avoid relying on color alone.

### Gestalt

- Proximity: related elements should be spatially grouped.
- Similarity: elements with similar meaning should share visual treatment.
- Continuity: layouts should guide the eye in a smooth, predictable path.
- Figure-ground: important content must stand apart clearly from the background.
- Alignment: elements should align to a clear visual structure.
- Closure: related content should feel visually contained or complete.

### Rams-Inspired Product Taste

- Useful: every element should support the user's task or understanding.
- Unobtrusive: the interface should not call attention to itself without reason.
- Honest: do not imply value, urgency, certainty, or capability the product does not provide.
- Long-lasting: prefer durable patterns over trend-driven effects.
- Thorough: details should feel considered, not arbitrary.
- As little design as possible: remove anything that does not strengthen meaning or usability.

### Nielsen-Inspired Usability

- Visibility of system status: show relevant states such as listening, thinking, speaking, reconnecting, loading, streaming, error, archived, active, and pinned.
- Match the real world: use language familiar to the user, especially around memory, evidence, and recovery.
- User control and freedom: allow dismissal, close, back out, undo, correction, and recovery where possible.
- Consistency and standards: follow known interaction conventions unless there is a strong reason not to.
- Error prevention: make destructive or high-impact actions hard to do accidentally.
- Recognition over recall: make options visible instead of forcing the user to remember hidden gestures or modes.
- Aesthetic and minimalist design: remove irrelevant information.
- Help users recover: error messages should be specific, constructive, and calm.

## Product-Specific Rules

### Voice Mode

- The orb should remain the hero of voice mode.
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
- Archived, pinned, active, and outdated memories must be visually and textually distinguishable.
- Evidence should be easy to scan before it is detailed.
- Memory UI must be honest about uncertainty. Do not make inferred beliefs feel like facts.

### Proactive Insights

- A proactive insight should earn its interruption.
- The UI should make dismissal easy and non-punitive.
- Copy should be concrete and useful, not vaguely therapeutic.
- Do not create a feed of generic insights. One strong insight beats several weak ones.

## Components And Controls

- Use icon buttons for compact actions when the icon is familiar: microphone, send, close, refresh, atlas.
- Use text labels when the action is unfamiliar, high-stakes, or benefits from explicit wording.
- Use segmented controls for mutually exclusive modes, as in voice/chat.
- Use tabs for alternate views within a single surface, as in map/timeline/patterns.
- Use chips for compact metadata, statuses, counts, and categories.
- Use flyouts for focused inspection when the user needs context without leaving the current surface.
- Primary action should have one dominant treatment. Secondary actions should be visually quieter.
- Keep touch targets at least 44 by 44 px where possible.
- Controls must have accessible labels when the visible UI is icon-only.

## Typography And Copy

- Copy should be concise, specific, and front-loaded.
- Prefer plain words over brand mood.
- Avoid generic AI language such as "unlock your potential", "supercharge", "seamless", or "personalized experience" unless the surrounding sentence makes it concrete.
- Use sentence case for most interface copy.
- Use uppercase sparingly for small labels, metadata, and compact status text.
- Do not over-explain features inside the active product surface. Put deeper explanations in inspection, help, or empty states.
- Never imply the companion knows more than the data supports.

Good:

- "What I remember, how strongly, and why."
- "Select a memory to inspect it."
- "Distilled from repeated reinforcement rather than one clear episode."

Weak:

- "Your intelligent AI memory hub."
- "Unlock deeper insights from your personalized companion."
- "Everything you need, all in one place."

## Color And Contrast

- Keep the dark canvas stable across screens.
- Cyan/blue should primarily communicate companion presence, memory, active system state, and successful connection.
- Violet/pink should primarily communicate user-side input, contrast, or relationship.
- Amber/orange should primarily communicate thinking, caution, salience, or transition.
- Use red/pink error tones only for actual errors.
- Do not rely on color alone for status. Pair color with labels, icons, shape, opacity, or placement.
- Check contrast for all text, especially muted labels on translucent dark surfaces.

## Layout And Spacing

- Favor a clear central axis for the primary experience.
- Use stable dimensions for fixed-format UI such as the orb, mode toggle, microphone button, lens items, composer, and atlas controls.
- Maintain consistent spacing within groups and larger spacing between groups.
- Avoid nested cards and excessive panels.
- Do not let text overlap controls, decorative fields, or other text at mobile or desktop sizes.
- Keep dense operational UI restrained and scannable rather than hero-like.

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

## Transformation Playbook

- Multiple equal-weight CTAs: choose one primary action and demote the rest.
- Cluttered screen: remove low-value sections, reduce repeated content, and increase spacing between groups.
- Messy layout: strengthen alignment, unify spacing, and normalize component treatments.
- Generic copy: rewrite the headline and support text to be concrete and front-loaded.
- Hard form: reduce field count, stack fields in one column, put labels above inputs, and replace dropdowns when a better control exists.
- Trendy but weak style: remove decorative effects that reduce contrast, hierarchy, or long-term durability.
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
- Does the change preserve the companion's calm, voice-first, memory-transparent identity?

If the answer to any of these is weak, revise before adding more design.
