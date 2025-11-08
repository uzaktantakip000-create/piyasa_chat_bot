import { forwardRef } from 'react'
import { Loader2 } from 'lucide-react'
import { cn } from './utils'

const buttonVariants = {
  default:
    'bg-primary text-primary-foreground shadow hover:bg-primary/90',
  destructive:
    'bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90',
  outline:
    'border border-input bg-background hover:bg-accent hover:text-accent-foreground',
  secondary:
    'bg-secondary text-secondary-foreground hover:bg-secondary/80',
  ghost: 'hover:bg-accent hover:text-accent-foreground',
  link: 'text-primary underline-offset-4 hover:underline',
  success: 'bg-success-bg text-success-text border border-success-border hover:bg-success-bg/80',
  warning: 'bg-warning-bg text-warning-text border border-warning-border hover:bg-warning-bg/80',
}

const buttonSizes = {
  xs: 'h-7 px-2 text-xs',
  sm: 'h-9 px-3 text-sm',
  default: 'h-10 px-4 py-2',
  lg: 'h-11 px-8 text-base',
  xl: 'h-12 px-10 text-lg',
  icon: 'h-10 w-10',
  'icon-sm': 'h-8 w-8',
  'icon-lg': 'h-12 w-12',
}

export const Button = forwardRef(
  (
    {
      className,
      variant = 'default',
      size = 'default',
      type = 'button',
      loading = false,
      disabled = false,
      children,
      ...props
    },
    ref
  ) => {
    const isDisabled = disabled || loading;

    return (
      <button
        type={type}
        disabled={isDisabled}
        className={cn(
          'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md font-medium',
          'transition-all duration-200',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
          'disabled:pointer-events-none disabled:opacity-50',
          buttonVariants[variant] ?? buttonVariants.default,
          buttonSizes[size] ?? buttonSizes.default,
          className
        )}
        ref={ref}
        {...props}
      >
        {loading && (
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        )}
        {children}
      </button>
    )
  }
)

Button.displayName = 'Button'
