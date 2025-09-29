import { forwardRef, useEffect, useState } from 'react'
import { cn } from './utils'

export const Progress = forwardRef(({ className, value = 0, max = 100, ...props }, ref) => {
  const [progress, setProgress] = useState(value)

  useEffect(() => {
    setProgress(value)
  }, [value])

  const percentage = Math.max(0, Math.min(100, (progress / max) * 100))

  return (
    <div
      ref={ref}
      role="progressbar"
      aria-valuenow={Math.round(percentage)}
      aria-valuemin={0}
      aria-valuemax={100}
      className={cn('relative h-2 w-full overflow-hidden rounded-full bg-muted', className)}
      {...props}
    >
      <div
        className="h-full bg-primary transition-all"
        style={{ width: `${percentage}%` }}
      />
    </div>
  )
})

Progress.displayName = 'Progress'
