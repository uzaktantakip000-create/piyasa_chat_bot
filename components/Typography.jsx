import React from 'react';
import { cn } from '../lib/utils';

/**
 * Typography Components - Semantic heading and text components
 *
 * Usage:
 * <H1>Page Title</H1>
 * <H2>Section Title</H2>
 * <Text variant="muted">Helper text</Text>
 */

// ============================================================================
// HEADINGS
// ============================================================================

export const H1 = React.forwardRef(({ className, children, ...props }, ref) => {
  return (
    <h1
      ref={ref}
      className={cn(
        'text-4xl font-bold leading-tight tracking-tight',
        'scroll-m-20',
        className
      )}
      {...props}
    >
      {children}
    </h1>
  );
});
H1.displayName = 'H1';

export const H2 = React.forwardRef(({ className, children, ...props }, ref) => {
  return (
    <h2
      ref={ref}
      className={cn(
        'text-3xl font-semibold leading-tight tracking-tight',
        'scroll-m-20',
        className
      )}
      {...props}
    >
      {children}
    </h2>
  );
});
H2.displayName = 'H2';

export const H3 = React.forwardRef(({ className, children, ...props }, ref) => {
  return (
    <h3
      ref={ref}
      className={cn(
        'text-2xl font-semibold leading-snug',
        'scroll-m-20',
        className
      )}
      {...props}
    >
      {children}
    </h3>
  );
});
H3.displayName = 'H3';

export const H4 = React.forwardRef(({ className, children, ...props }, ref) => {
  return (
    <h4
      ref={ref}
      className={cn(
        'text-xl font-semibold leading-snug',
        'scroll-m-20',
        className
      )}
      {...props}
    >
      {children}
    </h4>
  );
});
H4.displayName = 'H4';

export const H5 = React.forwardRef(({ className, children, ...props }, ref) => {
  return (
    <h5
      ref={ref}
      className={cn(
        'text-lg font-medium leading-normal',
        'scroll-m-20',
        className
      )}
      {...props}
    >
      {children}
    </h5>
  );
});
H5.displayName = 'H5';

export const H6 = React.forwardRef(({ className, children, ...props }, ref) => {
  return (
    <h6
      ref={ref}
      className={cn(
        'text-base font-medium leading-normal',
        'scroll-m-20',
        className
      )}
      {...props}
    >
      {children}
    </h6>
  );
});
H6.displayName = 'H6';

// ============================================================================
// TEXT VARIANTS
// ============================================================================

const textVariants = {
  default: 'text-base text-foreground',
  muted: 'text-sm text-muted-foreground',
  small: 'text-sm text-foreground',
  large: 'text-lg text-foreground',
  lead: 'text-xl text-muted-foreground font-light',
  subtle: 'text-sm text-muted-foreground',
  error: 'text-sm text-error-text',
  success: 'text-sm text-success-text',
  warning: 'text-sm text-warning-text',
  info: 'text-sm text-info-text',
};

export const Text = React.forwardRef(
  ({ className, variant = 'default', as: Component = 'p', children, ...props }, ref) => {
    return (
      <Component
        ref={ref}
        className={cn(textVariants[variant], className)}
        {...props}
      >
        {children}
      </Component>
    );
  }
);
Text.displayName = 'Text';

// ============================================================================
// LABEL (for form fields)
// ============================================================================

export const Label = React.forwardRef(({ className, children, required, ...props }, ref) => {
  return (
    <label
      ref={ref}
      className={cn(
        'text-sm font-medium leading-none',
        'peer-disabled:cursor-not-allowed peer-disabled:opacity-70',
        className
      )}
      {...props}
    >
      {children}
      {required && <span className="text-destructive ml-1">*</span>}
    </label>
  );
});
Label.displayName = 'Label';

// ============================================================================
// HELPER TEXT (for form fields)
// ============================================================================

export const HelperText = React.forwardRef(({ className, error, children, ...props }, ref) => {
  return (
    <p
      ref={ref}
      className={cn(
        'text-xs mt-1',
        error ? 'text-error-text' : 'text-muted-foreground',
        className
      )}
      {...props}
    >
      {children}
    </p>
  );
});
HelperText.displayName = 'HelperText';

// ============================================================================
// CODE (inline code)
// ============================================================================

export const Code = React.forwardRef(({ className, children, ...props }, ref) => {
  return (
    <code
      ref={ref}
      className={cn(
        'relative rounded bg-muted px-[0.3rem] py-[0.2rem]',
        'font-mono text-sm font-semibold',
        className
      )}
      {...props}
    >
      {children}
    </code>
  );
});
Code.displayName = 'Code';

// ============================================================================
// BLOCKQUOTE
// ============================================================================

export const Blockquote = React.forwardRef(({ className, children, ...props }, ref) => {
  return (
    <blockquote
      ref={ref}
      className={cn(
        'mt-6 border-l-2 border-border pl-6 italic',
        className
      )}
      {...props}
    >
      {children}
    </blockquote>
  );
});
Blockquote.displayName = 'Blockquote';

// ============================================================================
// LIST
// ============================================================================

export const List = React.forwardRef(
  ({ className, ordered = false, children, ...props }, ref) => {
    const Component = ordered ? 'ol' : 'ul';
    return (
      <Component
        ref={ref}
        className={cn(
          'my-6 ml-6',
          ordered ? 'list-decimal' : 'list-disc',
          '[&>li]:mt-2',
          className
        )}
        {...props}
      >
        {children}
      </Component>
    );
  }
);
List.displayName = 'List';

// ============================================================================
// EXPORT ALL
// ============================================================================

export default {
  H1,
  H2,
  H3,
  H4,
  H5,
  H6,
  Text,
  Label,
  HelperText,
  Code,
  Blockquote,
  List,
};
