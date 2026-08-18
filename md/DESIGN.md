---
name: Kinetic Mapview System
colors:
  surface: '#f7f9fb'
  surface-dim: '#d8dadc'
  surface-bright: '#f7f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f6'
  surface-container: '#eceef0'
  surface-container-high: '#e6e8ea'
  surface-container-highest: '#e0e3e5'
  on-surface: '#191c1e'
  on-surface-variant: '#434655'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f3'
  outline: '#737686'
  outline-variant: '#c3c6d7'
  surface-tint: '#0053db'
  primary: '#004ac6'
  on-primary: '#ffffff'
  primary-container: '#2563eb'
  on-primary-container: '#eeefff'
  inverse-primary: '#b4c5ff'
  secondary: '#006c4a'
  on-secondary: '#ffffff'
  secondary-container: '#82f5c1'
  on-secondary-container: '#00714e'
  tertiary: '#943700'
  on-tertiary: '#ffffff'
  tertiary-container: '#bc4800'
  on-tertiary-container: '#ffede6'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dbe1ff'
  primary-fixed-dim: '#b4c5ff'
  on-primary-fixed: '#00174b'
  on-primary-fixed-variant: '#003ea8'
  secondary-fixed: '#85f8c4'
  secondary-fixed-dim: '#68dba9'
  on-secondary-fixed: '#002114'
  on-secondary-fixed-variant: '#005137'
  tertiary-fixed: '#ffdbcd'
  tertiary-fixed-dim: '#ffb596'
  on-tertiary-fixed: '#360f00'
  on-tertiary-fixed-variant: '#7d2d00'
  background: '#f7f9fb'
  on-background: '#191c1e'
  surface-variant: '#e0e3e5'
  border-subtle: '#E2E8F0'
  surface-glass: rgba(255, 255, 255, 0.85)
  status-shortlisted: '#3B82F6'
  status-warning: '#F59E0B'
  status-occupied: '#64748B'
typography:
  display-table:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: -0.01em
  headline-panel:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
  body-compact:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  label-caps:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.05em
  marker-id:
    fontFamily: Inter
    fontSize: 10px
    fontWeight: '700'
    lineHeight: 12px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  rail-width: 64px
  panel-margin: 16px
  gutter-dense: 8px
  cell-padding: 6px 12px
---

## Brand & Style
The design system is engineered for high-stakes operational environments where information density and spatial awareness are paramount. It targets real estate professionals managing high-volume NYC/NJ rental portfolios. 

The aesthetic is **Professional/Modern with Glassmorphism**. It utilizes a "Map-First" philosophy where the interface sits atop a geographic canvas. By employing subtle transparency, fine borders, and a desaturated palette, the system ensures that complex data remains legible without overwhelming the user. The emotional response is one of precision, control, and calm efficiency.

## Colors
The palette is intentionally restrained to maintain focus on data indicators.
- **Primary (Blue):** Used for selection states, active navigation, and primary "Shortlisted" markers.
- **Secondary (Green):** Reserved for "Available" or "Success" states within the rental funnel.
- **Neutral:** A range of Slate grays (from `#F8FAFC` to `#1E293B`) provides the structural skeleton. 
- **Surface Strategy:** Backgrounds are predominantly white or near-white. Floating panels use a semi-transparent "glass" effect to maintain a sense of place relative to the map beneath.

## Typography
This design system uses **Inter** exclusively to leverage its exceptional legibility at small sizes. 
- **Density:** We prioritize smaller font sizes (11px–14px) to maximize the "Command Center" feel. 
- **Hierarchy:** Contrast is achieved through font-weight (SemiBold/Bold) and letter spacing rather than large size increases. 
- **Labels:** Use `label-caps` for table headers and category descriptors to differentiate them from actionable data.

## Layout & Spacing
The layout follows a **Fixed-Fluid Hybrid** model optimized for ultra-wide monitors.
- **Navigation Rail:** A slim, fixed 64px vertical bar on the left for top-level switching.
- **Floating Panels:** Operational units (Filters, Details, Lists) float 16px from the screen edges with a consistent 8px internal gutter.
- **Data Tables:** High-density grids utilize 6px vertical padding to allow for maximum row visibility without scrolling.
- **Map Viewport:** The map acts as the global "Level 0" background, filling 100% of the viewport behind the floating UI.

## Elevation & Depth
Depth is communicated through **Glassmorphism and Tonal Layering** rather than heavy shadows.
- **Base Layer:** The Map.
- **Mid Layer:** Floating panels with a `backdrop-filter: blur(12px)` and a 1px `border-subtle`.
- **Top Layer:** Popovers and Tooltips, which use a slightly more opaque white and a soft, diffused ambient shadow (8% opacity) to denote immediate interaction.
- **Borders:** Use 1px solid strokes for all container definitions to maintain the "instrument cluster" precision.

## Shapes
We adopt a **Soft (4px)** corner radius. This provides a professional, "tooled" look that feels more precise than rounder consumer apps, while remaining more approachable than a strictly sharp-edged "Brutalist" interface. Map markers use the same 4px radius, creating a unified language between the UI and the spatial data.

## Components
- **Map Markers:** Rectangular containers with a colored left-accent bar (State) and a 10px ID label. Shortlisted properties use the Primary Blue; Warnings use Amber.
- **Navigation Rail:** Minimalist icons only. Active states use a subtle side-glow or "active-pill" indicator.
- **Compact Filter Chips:** Low-profile, gray-background chips that turn Primary Blue when active. No heavy shadows; 1px border only.
- **Dense Data Tables:** Border-bottom-only rows with "zebra-striping" on hover to assist eye-tracking across wide rows.
- **Floating Panels:** Modular units with a header containing "Collapse" and "Close" controls to allow users to customize their workspace density.
- **Input Fields:** 32px height (compact), using an inset 1px border that thickens only on focus.