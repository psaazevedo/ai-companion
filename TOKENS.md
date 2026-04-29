# Design Tokens

Raw design values for the AI companion. `DESIGN.md` explains how to use them. Update this file only when the visual system changes.

## Color Roles

### Background

| Token | Value | Use |
|---|---|---|
| `bg.base` | `#080B14` | App canvas |
| `bg.surface` | `#0B1020` | Cards, composer, quiet panels |
| `bg.surfaceRaised` | `#0E1423` | Elevated panels, state cards |
| `bg.control` | `#0D1321` | Buttons and compact controls |
| `bg.overlay` | `rgba(8, 11, 20, 0.985)` | Full-screen overlays |
| `bg.translucent` | `rgba(7, 12, 24, 0.82)` | Floating surfaces |

### Text

| Token | Value | Use |
|---|---|---|
| `text.primary` | `#F4F8FF` | Primary readable text |
| `text.secondary` | `#D3DEF3` | Secondary readable text |
| `text.muted` | `#8FA4CC` | Supporting labels |
| `text.tertiary` | `#7488B0` | Placeholders and low-emphasis hints |
| `text.inverse` | `#08101D` | Text/icons on light active controls |

### Presence And Relationship

| Token | Value | Use |
|---|---|---|
| `presence.cyan` | `#84ECFF` | Listening, memory, primary active state |
| `presence.blue` | `#66A6FF` | Companion/system accent |
| `presence.softBlue` | `#AFC2E6` | Inactive icon state |
| `user.violet` | `#E28FFF` | User-side input and contrast |
| `user.pink` | `#FF58DE` | Relational accent, rarely used |

### State

| Token | Value | Use |
|---|---|---|
| `state.speaking` | `#8DE7C2` | Speaking/successful flow |
| `state.thinking` | `#FFC785` | Thinking, salience, caution |
| `state.warning` | `#FFD86B` | Warning or pinned status |
| `state.error` | `#FF9FB5` | Errors only |
| `state.archived` | `#8F9BB4` | Archived or inactive memory |

### Borders And Glows

| Token | Value | Use |
|---|---|---|
| `border.subtle` | `rgba(145, 190, 255, 0.12)` | Default quiet border |
| `border.active` | `rgba(146, 229, 255, 0.24)` | Active or focused border |
| `border.strong` | `rgba(244, 248, 255, 0.28)` | High-contrast border |
| `glow.cyan.soft` | `rgba(132, 236, 255, 0.16)` | Functional elevation |
| `glow.cyan.medium` | `rgba(132, 236, 255, 0.28)` | Active presence |

## Spacing

Use this scale before inventing a new value:

| Token | Value | Use |
|---|---:|---|
| `space.1` | `4` | Tight icon/detail gap |
| `space.2` | `8` | Small internal gap |
| `space.3` | `12` | Component gap |
| `space.4` | `16` | Standard internal padding |
| `space.5` | `20` | Dense panel padding |
| `space.6` | `24` | Standard outer padding |
| `space.8` | `32` | Component separation |
| `space.10` | `40` | Large internal block gap |
| `space.12` | `48` | Section gap |
| `space.16` | `64` | Major section gap |
| `space.20` | `80` | Large screen section gap |

Current implementation may contain transitional custom values. New work should prefer the scale unless a fixed-format element requires a specific dimension.

## Radius

| Token | Value | Use |
|---|---:|---|
| `radius.sm` | `8` | Small inputs, compact surfaces |
| `radius.md` | `12` | Standard controls |
| `radius.lg` | `18` | Composer and medium panels |
| `radius.xl` | `24` | Floating cards and state blocks |
| `radius.2xl` | `32` | Large flyouts and immersive panels |
| `radius.pill` | `999` | Circular buttons, pills, orb elements |

Avoid large radii on ordinary operational UI unless matching an existing product surface.

## Typography

| Token | Size | Weight | Line height | Use |
|---|---:|---:|---:|---|
| `type.display` | `28-40` | `700-800` | `1.1-1.2` | Major surface headers |
| `type.title` | `22-28` | `600-800` | `1.15-1.25` | Titles |
| `type.subtitle` | `18-20` | `600-700` | `1.25-1.35` | Section titles |
| `type.body` | `14-16` | `400-500` | `1.45-1.65` | Main content |
| `type.bodyLarge` | `17-19` | `500` | `1.45` | Focused chat answer |
| `type.caption` | `11-13` | `500-700` | `1.25-1.4` | Labels, helper text |
| `type.eyebrow` | `10-12` | `700-800` | `1.2` | Uppercase metadata |

## Motion

| Token | Value | Use |
|---|---|---|
| `motion.easeEnter` | `cubic-bezier(0.22, 1, 0.36, 1)` | Element entry |
| `motion.easeExit` | `cubic-bezier(0.55, 0, 1, 0.45)` | Element exit |
| `motion.easeMode` | `Easing.inOut(Easing.cubic)` | Major mode shifts |
| `motion.easeLoop` | `Easing.inOut(Easing.sin)` | Idle loops |
| `motion.fast` | `80-150ms` | Press, hover, focus |
| `motion.short` | `180-250ms` | Small appear/fade |
| `motion.panel` | `240-360ms` | Drawer, flyout, modal |
| `motion.overlay` | `420-520ms` | Large overlay |
| `motion.mode` | `620-720ms` | Voice/chat transition |
| `motion.ambient` | `3-8s` | Orb and breathing loops |

## Fixed Dimensions

| Token | Value | Use |
|---|---:|---|
| `target.minimum` | `44` | Minimum touch target |
| `orb.heroStage` | `560` | Web orb stage |
| `orb.nativeFrame` | `220` | Native hero orb frame |
| `orb.nativeCompact` | `112` | Native compact orb frame |
| `button.mic` | `52` | Voice microphone button |
| `toggle.optionWidth` | `48` | Mode toggle option width |
| `toggle.optionHeight` | `40` | Mode toggle option height |
| `composer.minHeight` | `76` | Chat composer shell |
| `composer.inputMin` | `50` | Composer input minimum |
| `composer.inputMax` | `156` | Composer input maximum |
| `chat.lensItemHeight` | `300` | Chat lens snap interval |
| `atlas.toggle` | `44` | Atlas floating toggle |
| `atlas.flyoutWidth` | `390` | Memory detail flyout |

