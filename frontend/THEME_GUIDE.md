# AI Prompt Enhancer Theme Specification

This theme guide defines the visual identity and branding tokens used across the **AI Prompt Enhancer** website. You can copy these color palettes, custom gradients, glows, and shadow configurations to maintain brand consistency in any other project, web application, or design tool.

---

## 🎨 Color Palette Reference

| Name | Hex Code | Purpose |
|:---|:---|:---|
| **Purple (Indigo)** | `#6366F1` | Core Primary Brand Accent |
| **Violet** | `#8B5CF6` | Core Brand Accent & UI states |
| **Deep Violet** | `#7C3AED` | Hover states & secondary brand accent |
| **Pink** | `#EC4899` | Accent color & highlights |
| **Lavender** | `#A78BFA` | Lighter brand accent |
| **Blue** | `#60A5FA` | Info status & light brand highlight |
| **Ink (Dark Neutral)** | `#09090B` | Headings & dark interface elements |
| **Dark Gray** | `#0A0A0A` | Body text color |
| **White** | `#FFFFFF` | Main page and component backgrounds |
| **Light BG** | `#FAFAFC` | Section backgrounds & card backing |
| **Surface** | `#FAFAFA` | Panel backgrounds |
| **Border** | `#F3F4F6` | Subtle borders & dividers |

### Neutral Grayscale Palette
* **Gray 100:** `#F4F4F5`
* **Gray 200:** `#E5E7EB`
* **Gray 300:** `#D1D5DB`
* **Gray 400:** `#9CA3AF`
* **Gray 500:** `#6B7280`
* **Gray 600:** `#4B5563`
* **Gray 700:** `#374151`
* **Gray 800:** `#1F2937`

---

## ✨ Gradients & Special Effects

### Brand Text & Background Gradients
* **Primary Brand Gradient:** `linear-gradient(135deg, #6366F1 0%, #8B5CF6 40%, #EC4899 100%)`
* **Lavender to Pink Gradient:** `linear-gradient(135deg, #A78BFA 0%, #8B5CF6 55%, #EC4899 100%)`

### Radial Glow Gradients (For AI Glassmorphism Backgrounds)
* **Purple Glow:** `radial-gradient(circle, rgba(139, 92, 246, 0.15) 0%, transparent 70%)`
* **Pink Glow:** `radial-gradient(circle, rgba(236, 72, 153, 0.12) 0%, transparent 70%)`
* **Blue Glow:** `radial-gradient(circle, rgba(96, 165, 250, 0.12) 0%, transparent 70%)`

---

## 👥 Consistent Shadows (Premium Cards)
Use these soft shadow values combined with a light border (`border: 1px solid rgba(9, 9, 11, 0.055)`) to match the premium card look:
* **Standard Card Shadow:** `0 1px 3px rgba(0, 0, 0, 0.04), 0 4px 12px rgba(0, 0, 0, 0.04), 0 8px 32px rgba(99, 102, 241, 0.06)`
* **Large Card Shadow:** `0 2px 4px rgba(0, 0, 0, 0.03), 0 8px 24px rgba(0, 0, 0, 0.05), 0 16px 48px rgba(99, 102, 241, 0.08)`

---

## 🚀 Copy-Paste Integration Snippets

### 1. Plain CSS Custom Variables
Add this block inside your CSS file (typically `globals.css` or `index.css`) to make all color styles available via `var(--...)`:
```css
:root {
  /* Colors */
  --color-brand-purple: #6366F1;
  --color-brand-violet: #8B5CF6;
  --color-brand-indigo: #7C3AED;
  --color-brand-pink: #EC4899;
  --color-brand-blue: #60A5FA;
  --color-brand-lavender: #A78BFA;
  --color-brand-purple-light: #A855F7;
  
  --color-ink: #09090B;
  --color-foreground: #0A0A0A;
  --color-background: #FFFFFF;
  --color-bg-light: #FAFAFC;
  --color-surface: #FAFAFA;
  --color-border: #F3F4F6;

  /* Gradients */
  --gradient-primary: linear-gradient(135deg, var(--color-brand-purple) 0%, var(--color-brand-violet) 40%, var(--color-brand-pink) 100%);
  --gradient-lavender-pink: linear-gradient(135deg, var(--color-brand-lavender) 0%, var(--color-brand-violet) 55%, var(--color-brand-pink) 100%);
}
```

### 2. Tailwind CSS Configuration (v3)
Add this to your `tailwind.config.js` to extend classes with these names (e.g. `bg-brand-purple`, `text-brand-violet`):
```javascript
/** @type {import('tailwindcss').Config} */
module.exports = {
  theme: {
    extend: {
      colors: {
        brand: {
          purple: '#6366F1',
          violet: '#8B5CF6',
          indigo: '#7C3AED',
          pink: '#EC4899',
          blue: '#60A5FA',
          lavender: '#A78BFA',
          'purple-light': '#A855F7',
        },
        ink: '#09090B',
        surface: '#FAFAFA',
      },
      backgroundImage: {
        'brand-gradient': 'linear-gradient(135deg, #6366F1 0%, #8B5CF6 40%, #EC4899 100%)',
        'lavender-pink': 'linear-gradient(135deg, #A78BFA 0%, #8B5CF6 55%, #EC4899 100%)',
      },
      boxShadow: {
        'card-soft': '0 1px 3px rgba(0, 0, 0, 0.04), 0 4px 12px rgba(0, 0, 0, 0.04), 0 8px 32px rgba(99, 102, 241, 0.06)',
        'card-soft-lg': '0 2px 4px rgba(0, 0, 0, 0.03), 0 8px 24px rgba(0, 0, 0, 0.05), 0 16px 48px rgba(99, 102, 241, 0.08)',
      }
    },
  },
}
```

### 3. Tailwind CSS Config (v4 - `@theme inline`)
Add this to your main CSS file setup:
```css
@import "tailwindcss";

@theme inline {
  --color-brand-purple: #6366F1;
  --color-brand-violet: #8B5CF6;
  --color-brand-indigo: #7C3AED;
  --color-brand-pink: #EC4899;
  --color-brand-blue: #60A5FA;
  --color-brand-lavender: #A78BFA;
  --color-brand-purple-light: #A855F7;
  
  --color-ink: #09090B;
  --color-surface: #FAFAFA;
}
```

### 4. JavaScript/Figma Object Structure
```json
{
  "purple": "#6366F1",
  "violet": "#8B5CF6",
  "indigo": "#7C3AED",
  "pink": "#EC4899",
  "blue": "#60A5FA",
  "lavender": "#A78BFA",
  "ink": "#09090B",
  "bg": "#FAFAFC"
}
```
