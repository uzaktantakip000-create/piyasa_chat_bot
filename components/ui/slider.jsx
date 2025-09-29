import { forwardRef, useEffect, useState } from 'react'
import { cn } from './utils'

export const Slider = forwardRef(
  (
    { className, value, defaultValue = [0], min = 0, max = 100, step = 1, disabled = false, onValueChange, ...props },
    ref
  ) => {
    const isControlled = Array.isArray(value)
    const [internalValue, setInternalValue] = useState(() => {
      if (isControlled) {
        return Number(value[0] ?? min)
      }
      return Number(defaultValue[0] ?? min)
    })

    useEffect(() => {
      if (isControlled) {
        setInternalValue(Number(value[0] ?? min))
      }
    }, [isControlled, value, min])

    const handleChange = (event) => {
      const next = Number(event.target.value)
      if (!isControlled) {
        setInternalValue(next)
      }
      onValueChange?.([next])
    }

    return (
      <input
        type="range"
        ref={ref}
        min={min}
        max={max}
        step={step}
        value={internalValue}
        onChange={handleChange}
        disabled={disabled}
        className={cn(
          'h-2 w-full cursor-pointer appearance-none rounded-full bg-muted accent-primary disabled:cursor-not-allowed',
          className
        )}
        {...props}
      />
    )
  }
)

Slider.displayName = 'Slider'
