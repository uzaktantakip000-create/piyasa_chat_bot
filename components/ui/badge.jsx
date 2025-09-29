import { forwardRef } from 'react'
import { cn } from './utils'

const badgeVariants = {
  default: 'bg-primary text-primary-foreground hover:bg-primary/80',
  secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/80',
  outline: 'text-foreground border border-border'
}

export const Badge = forwardRef(({ className, variant = 'default', ...props }, ref) => (
  <span
    ref={ref}
    className={cn(
      'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors',
      badgeVariants[variant] ?? badgeVariants.default,
      className
    )}
    {...props}
  />
))
Badge.displayName = 'Badge'
