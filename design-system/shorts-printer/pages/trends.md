# Trends Page Overrides

> **PROJECT:** Shorts Printer
> **Generated:** 2026-10-13 23:49:27
> **Page Type:** Dashboard / Data View

> ⚠️ **IMPORTANT:** Rules in this file **override** the Master file (`design-system/MASTER.md`).
> Only deviations from the Master are documented here. For all other rules, refer to the Master.

---

## Page-Specific Rules

### Layout Overrides

- **Max Width:** 1400px or full-width
- **Grid:** 12-column grid for data flexibility

### Spacing Overrides

- **Content Density:** High — optimize for information display

### Typography Overrides

- No overrides — use Master typography

### Color Overrides

- No overrides — use Master colors

### Component Overrides

- Avoid: Overflow or broken layout
- Avoid: Lorem ipsum everywhere
- Avoid: Auto-advance slides without a stop control

---

## Page-Specific Components

- No unique components for this page

---

## Recommendations

- Effects: Hover tooltips, chart zoom on click, row highlighting on hover, smooth filter animations, data loading spinners
- Content: Truncate with ellipsis and expand option
- Content: Use realistic sample data
- Animation: Provide previous next and play/pause; stop on focus or hover and when reduced motion is requested

---

## Applied in this project (extra searches)

- Video preview is click-to-play (ux: Sustainability). The thumbnail button turns into a `youtube-nocookie` iframe only on click, with no autoplay on load. Polling skips any fragment that has an iframe, so playback is never cut.
- Charts use direct labels and no color-only encoding (chart). Weight bars and the total bar always show the number beside them (`35`, `82/100`), and score pips have `aria-label="5점 중 n점"`.
- Progress uses step indicators: a 3-node `<ol>` stepper with `aria-current="step"`, and the analyze node shows `done/total` alongside a `role="progressbar"` bar.
- Empty states come with an action: each stage card says what will appear next, and the list empty state points to [분석 시작].
- Rejected: hover tooltips, chart zoom and smooth filter animations from the generated recommendations (motion 3, tool screen).
