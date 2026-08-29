# Design QA — Tablet Energy Flow Prototype

- Source visual truth: `/home/user/projects/MySmartHome/output/tablet-panel-concepts/variant-5-energy-flow.png`
- Implementation screenshot: `/home/user/projects/MySmartHome/output/playwright/tablet-energy-flow-prototype.png`
- Combined evidence: `/home/user/projects/MySmartHome/output/playwright/tablet-energy-flow-comparison.png`
- Viewport: 1280 × 800 CSS px, device scale factor 1.
- Source pixels: 1586 × 992; normalized to 1280 × 800 for comparison.
- Implementation pixels: 1280 × 800.
- State: default healthy-home state, rainy twilight, live flows active.

## Full-view comparison evidence

The implementation preserves the selected direction's dominant house cutaway, blue-hour photographic atmosphere, left safety/energy stack, top status bar, interactive system labels, bottom active-device dock, and confirmed quick modes. The information hierarchy, major-region proportions, palette, image treatment, and Russian copy remain aligned after density normalization.

## Focused-region evidence

The safety and energy stack, house hotspot labels, and bottom dock were inspected in the 1280 × 800 browser capture. Text remains readable and unclipped; status colors map consistently to green health, cyan electricity/water, and amber heat. The generated house asset is sharp at the rendered crop and contains no embedded UI.

## Findings

- No actionable P0, P1, or P2 mismatches remain.
- P3: the reference uses a denser branching network of visible flow routes. The prototype deliberately uses fewer animated routes so the photo remains legible and the motion does not become distracting.
- P3: the generated background is not the homeowner's actual house. It is a concept asset and must be replaced or approved before production use.

## Interaction verification

- Opened an electricity hotspot and verified the contextual confirmed-state panel.
- Opened the `Ушёл` mode, verified the confirmation dialog, and confirmed the mode.
- Verified refresh loading feedback.
- Browser console after reload and interaction: 0 errors, 0 warnings.
- `prefers-reduced-motion` fallback is present.

## Comparison history

1. Initial capture: one missing favicon request appeared in the browser console.
2. Fix: added the generated house asset as the page favicon.
3. Post-fix evidence: primary interactions passed and the console reported 0 errors and 0 warnings.

## Implementation checklist

- [x] Photographic cutaway hero asset installed.
- [x] Animated rain, ambient camera drift, flow particles, pulses, and transitions.
- [x] Interactive system hotspots.
- [x] Confirmation before quick-mode state changes.
- [x] Responsive fallback and reduced-motion behavior.
- [x] Production Home Assistant remains untouched.

final result: passed
