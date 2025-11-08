/**
 * Design Tokens - Central design system configuration
 *
 * This file defines all design tokens used across the application.
 * Tokens are organized by category: colors, typography, spacing, etc.
 */

// ============================================================================
// COLORS
// ============================================================================

/**
 * Semantic color palette
 * Maps to CSS variables defined in index.css
 */
export const colors = {
  // Primary brand colors
  primary: {
    DEFAULT: 'hsl(var(--primary))',
    foreground: 'hsl(var(--primary-foreground))',
  },

  // Secondary colors
  secondary: {
    DEFAULT: 'hsl(var(--secondary))',
    foreground: 'hsl(var(--secondary-foreground))',
  },

  // Destructive/error colors
  destructive: {
    DEFAULT: 'hsl(var(--destructive))',
    foreground: 'hsl(var(--destructive-foreground))',
  },

  // Muted/subtle colors
  muted: {
    DEFAULT: 'hsl(var(--muted))',
    foreground: 'hsl(var(--muted-foreground))',
  },

  // Accent colors
  accent: {
    DEFAULT: 'hsl(var(--accent))',
    foreground: 'hsl(var(--accent-foreground))',
  },

  // Backgrounds
  background: 'hsl(var(--background))',
  foreground: 'hsl(var(--foreground))',

  // Card colors
  card: {
    DEFAULT: 'hsl(var(--card))',
    foreground: 'hsl(var(--card-foreground))',
  },

  // Popover colors
  popover: {
    DEFAULT: 'hsl(var(--popover))',
    foreground: 'hsl(var(--popover-foreground))',
  },

  // Border colors
  border: 'hsl(var(--border))',
  input: 'hsl(var(--input))',
  ring: 'hsl(var(--ring))',

  // Status colors (semantic)
  status: {
    success: {
      bg: 'rgb(220 252 231)', // green-100
      text: 'rgb(22 101 52)', // green-800
      border: 'rgb(187 247 208)', // green-200
    },
    error: {
      bg: 'rgb(254 226 226)', // red-100
      text: 'rgb(153 27 27)', // red-800
      border: 'rgb(254 202 202)', // red-200
    },
    warning: {
      bg: 'rgb(254 243 199)', // amber-100
      text: 'rgb(146 64 14)', // amber-800
      border: 'rgb(253 230 138)', // amber-200
    },
    info: {
      bg: 'rgb(219 234 254)', // blue-100
      text: 'rgb(30 64 175)', // blue-800
      border: 'rgb(191 219 254)', // blue-200
    },
  },
} as const;

// ============================================================================
// TYPOGRAPHY
// ============================================================================

/**
 * Font size scale with corresponding line heights
 * Based on Tailwind's default scale with semantic naming
 */
export const typography = {
  fontSize: {
    xs: ['0.75rem', { lineHeight: '1rem' }],      // 12px
    sm: ['0.875rem', { lineHeight: '1.25rem' }],  // 14px
    base: ['1rem', { lineHeight: '1.5rem' }],     // 16px
    lg: ['1.125rem', { lineHeight: '1.75rem' }],  // 18px
    xl: ['1.25rem', { lineHeight: '1.75rem' }],   // 20px
    '2xl': ['1.5rem', { lineHeight: '2rem' }],    // 24px
    '3xl': ['1.875rem', { lineHeight: '2.25rem' }], // 30px
    '4xl': ['2.25rem', { lineHeight: '2.5rem' }], // 36px
    '5xl': ['3rem', { lineHeight: '1' }],         // 48px
    '6xl': ['3.75rem', { lineHeight: '1' }],      // 60px
  },

  fontWeight: {
    light: '300',
    normal: '400',
    medium: '500',
    semibold: '600',
    bold: '700',
  },

  // Semantic heading styles
  headings: {
    h1: {
      fontSize: '2.25rem',    // 36px
      lineHeight: '2.5rem',   // 40px
      fontWeight: '700',      // bold
      letterSpacing: '-0.025em',
    },
    h2: {
      fontSize: '1.875rem',   // 30px
      lineHeight: '2.25rem',  // 36px
      fontWeight: '600',      // semibold
      letterSpacing: '-0.025em',
    },
    h3: {
      fontSize: '1.5rem',     // 24px
      lineHeight: '2rem',     // 32px
      fontWeight: '600',      // semibold
    },
    h4: {
      fontSize: '1.25rem',    // 20px
      lineHeight: '1.75rem',  // 28px
      fontWeight: '600',      // semibold
    },
    h5: {
      fontSize: '1.125rem',   // 18px
      lineHeight: '1.75rem',  // 28px
      fontWeight: '500',      // medium
    },
    h6: {
      fontSize: '1rem',       // 16px
      lineHeight: '1.5rem',   // 24px
      fontWeight: '500',      // medium
    },
  },
} as const;

// ============================================================================
// SPACING
// ============================================================================

/**
 * Spacing scale (rem-based)
 * Based on 4px base unit (0.25rem)
 */
export const spacing = {
  0: '0',
  1: '0.25rem',   // 4px
  2: '0.5rem',    // 8px
  3: '0.75rem',   // 12px
  4: '1rem',      // 16px
  5: '1.25rem',   // 20px
  6: '1.5rem',    // 24px
  8: '2rem',      // 32px
  10: '2.5rem',   // 40px
  12: '3rem',     // 48px
  16: '4rem',     // 64px
  20: '5rem',     // 80px
  24: '6rem',     // 96px
  32: '8rem',     // 128px
  40: '10rem',    // 160px
  48: '12rem',    // 192px
  64: '16rem',    // 256px
} as const;

// ============================================================================
// BORDER RADIUS
// ============================================================================

/**
 * Border radius scale
 */
export const borderRadius = {
  none: '0',
  sm: 'calc(var(--radius) - 4px)',
  md: 'calc(var(--radius) - 2px)',
  lg: 'var(--radius)',
  xl: 'calc(var(--radius) + 4px)',
  '2xl': 'calc(var(--radius) + 8px)',
  full: '9999px',
} as const;

// ============================================================================
// SHADOWS
// ============================================================================

/**
 * Box shadow system
 */
export const shadows = {
  sm: '0 1px 2px 0 rgb(0 0 0 / 0.05)',
  md: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
  lg: '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
  xl: '0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)',
  '2xl': '0 25px 50px -12px rgb(0 0 0 / 0.25)',
  inner: 'inset 0 2px 4px 0 rgb(0 0 0 / 0.05)',
  none: '0 0 #0000',
} as const;

// ============================================================================
// TRANSITIONS
// ============================================================================

/**
 * Transition durations and easing functions
 */
export const transitions = {
  duration: {
    fast: '150ms',
    base: '200ms',
    slow: '300ms',
    slower: '500ms',
  },

  easing: {
    default: 'cubic-bezier(0.4, 0, 0.2, 1)',      // ease-in-out
    linear: 'linear',
    in: 'cubic-bezier(0.4, 0, 1, 1)',             // ease-in
    out: 'cubic-bezier(0, 0, 0.2, 1)',            // ease-out
    inOut: 'cubic-bezier(0.4, 0, 0.2, 1)',        // ease-in-out
  },
} as const;

// ============================================================================
// BREAKPOINTS
// ============================================================================

/**
 * Responsive breakpoints (matches Tailwind defaults)
 */
export const breakpoints = {
  sm: '640px',
  md: '768px',
  lg: '1024px',
  xl: '1280px',
  '2xl': '1536px',
} as const;

// ============================================================================
// Z-INDEX LAYERS
// ============================================================================

/**
 * Z-index scale for layering
 */
export const zIndex = {
  base: 0,
  dropdown: 1000,
  sticky: 1020,
  fixed: 1030,
  modalBackdrop: 1040,
  modal: 1050,
  popover: 1060,
  tooltip: 1070,
  notification: 1080,
} as const;

// ============================================================================
// COMPONENT-SPECIFIC TOKENS
// ============================================================================

/**
 * Button size variants
 */
export const buttonSizes = {
  sm: {
    height: '2rem',       // 32px
    paddingX: '0.75rem',  // 12px
    fontSize: '0.875rem', // 14px
  },
  md: {
    height: '2.5rem',     // 40px
    paddingX: '1rem',     // 16px
    fontSize: '1rem',     // 16px
  },
  lg: {
    height: '3rem',       // 48px
    paddingX: '1.5rem',   // 24px
    fontSize: '1.125rem', // 18px
  },
  icon: {
    size: '2.5rem',       // 40px square
  },
} as const;

/**
 * Input sizes
 */
export const inputSizes = {
  sm: {
    height: '2rem',       // 32px
    paddingX: '0.75rem',  // 12px
    fontSize: '0.875rem', // 14px
  },
  md: {
    height: '2.5rem',     // 40px
    paddingX: '1rem',     // 16px
    fontSize: '1rem',     // 16px
  },
  lg: {
    height: '3rem',       // 48px
    paddingX: '1.25rem',  // 20px
    fontSize: '1.125rem', // 18px
  },
} as const;

// ============================================================================
// EXPORT ALL
// ============================================================================

export const designTokens = {
  colors,
  typography,
  spacing,
  borderRadius,
  shadows,
  transitions,
  breakpoints,
  zIndex,
  buttonSizes,
  inputSizes,
} as const;

export default designTokens;
