import { createContext, forwardRef, useContext, useEffect, useMemo, useState } from 'react'
import { cn } from './utils'

const TabsContext = createContext(null)

export const Tabs = ({ value, defaultValue, onValueChange, className, children, ...props }) => {
  const isControlled = value !== undefined
  const [internalValue, setInternalValue] = useState(defaultValue)

  useEffect(() => {
    if (isControlled) {
      setInternalValue(value)
    }
  }, [isControlled, value])

  const setValue = (nextValue) => {
    if (!isControlled) {
      setInternalValue(nextValue)
    }
    onValueChange?.(nextValue)
  }

  const contextValue = useMemo(
    () => ({
      value: internalValue,
      setValue
    }),
    [internalValue]
  )

  return (
    <TabsContext.Provider value={contextValue}>
      <div className={className} {...props}>
        {children}
      </div>
    </TabsContext.Provider>
  )
}

export const TabsList = forwardRef(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      'inline-flex h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground',
      className
    )}
    {...props}
  />
))
TabsList.displayName = 'TabsList'

export const TabsTrigger = forwardRef(({ className, value, disabled = false, ...props }, ref) => {
  const context = useContext(TabsContext)
  if (!context) {
    throw new Error('TabsTrigger must be used within Tabs')
  }

  const isActive = context.value === value
  const handleClick = () => {
    if (disabled) {
      return
    }
    context.setValue(value)
  }

  return (
    <button
      type="button"
      role="tab"
      ref={ref}
      data-state={isActive ? 'active' : 'inactive'}
      aria-selected={isActive}
      disabled={disabled}
      onClick={handleClick}
      className={cn(
        'inline-flex min-w-[100px] items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
        isActive ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground',
        className
      )}
      {...props}
    />
  )
})
TabsTrigger.displayName = 'TabsTrigger'

export const TabsContent = forwardRef(({ className, value, ...props }, ref) => {
  const context = useContext(TabsContext)
  if (!context) {
    throw new Error('TabsContent must be used within Tabs')
  }

  if (context.value !== value) {
    return null
  }

  return (
    <div
      ref={ref}
      role="tabpanel"
      data-state="active"
      className={cn('mt-2 focus-visible:outline-none', className)}
      {...props}
    />
  )
})
TabsContent.displayName = 'TabsContent'
