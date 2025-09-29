import {
  createContext,
  forwardRef,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState
} from 'react'
import { createPortal } from 'react-dom'
import { cn } from './utils'

const SelectContext = createContext(null)

export const Select = ({ value, defaultValue, onValueChange, children }) => {
  const isControlled = value !== undefined
  const [internalValue, setInternalValue] = useState(defaultValue ?? '')
  const [items, setItems] = useState({})
  const [open, setOpen] = useState(false)
  const [triggerRect, setTriggerRect] = useState(null)

  useEffect(() => {
    if (isControlled) {
      setInternalValue(value ?? '')
    }
  }, [isControlled, value])

  const registerItem = (itemValue, label) => {
    setItems((prev) => {
      if (prev[itemValue] === label) {
        return prev
      }
      return { ...prev, [itemValue]: label }
    })
  }

  const handleSelect = (nextValue) => {
    if (!isControlled) {
      setInternalValue(nextValue)
    }
    onValueChange?.(nextValue)
    setOpen(false)
  }

  const contextValue = useMemo(
    () => ({
      value: internalValue,
      items,
      open,
      setOpen,
      select: handleSelect,
      registerItem,
      triggerRect,
      setTriggerRect
    }),
    [internalValue, items, open, triggerRect]
  )

  return <SelectContext.Provider value={contextValue}>{children}</SelectContext.Provider>
}

export const SelectTrigger = forwardRef(({ className, children, ...props }, ref) => {
  const context = useContext(SelectContext)
  if (!context) {
    throw new Error('SelectTrigger must be used within Select')
  }

  const { open, setOpen, setTriggerRect, items, value } = context
  const triggerRef = useRef(null)

  const updateRect = () => {
    if (triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect()
      const next = {
        top: rect.top + window.scrollY,
        left: rect.left + window.scrollX,
        width: rect.width,
        height: rect.height
      }
      setTriggerRect((prev) => {
        if (
          prev &&
          Math.abs(prev.top - next.top) < 0.5 &&
          Math.abs(prev.left - next.left) < 0.5 &&
          Math.abs(prev.width - next.width) < 0.5 &&
          Math.abs(prev.height - next.height) < 0.5
        ) {
          return prev
        }
        return next
      })
    }
  }

  useEffect(() => {
    updateRect()
  })

  useEffect(() => {
    if (!open) {
      return undefined
    }
    const handler = () => updateRect()
    window.addEventListener('resize', handler)
    window.addEventListener('scroll', handler, true)
    return () => {
      window.removeEventListener('resize', handler)
      window.removeEventListener('scroll', handler, true)
    }
  }, [open])

  const handleRef = (node) => {
    triggerRef.current = node
    updateRect()
    if (typeof ref === 'function') {
      ref(node)
    } else if (ref) {
      ref.current = node
    }
  }

  const toggleOpen = () => setOpen(!open)

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      toggleOpen()
    }
  }

  const selectedLabel = items[value] ?? ''

  return (
    <button
      type="button"
      ref={handleRef}
      onClick={toggleOpen}
      onKeyDown={handleKeyDown}
      aria-haspopup="listbox"
      aria-expanded={open}
      className={cn(
        'flex w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        className
      )}
      {...props}
    >
      <span className="flex-1 truncate text-left">
        {children ?? selectedLabel}
      </span>
      <svg
        className="ml-2 h-4 w-4 opacity-60"
        viewBox="0 0 20 20"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        aria-hidden="true"
      >
        <path d="M5 7l5 5 5-5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </button>
  )
})
SelectTrigger.displayName = 'SelectTrigger'

export const SelectValue = ({ placeholder, className }) => {
  const context = useContext(SelectContext)
  if (!context) {
    throw new Error('SelectValue must be used within Select')
  }

  const { value, items } = context
  const label = items[value]

  return (
    <span className={cn('block truncate', className)}>
      {label ?? value ?? placeholder ?? ''}
    </span>
  )
}

const SelectPortal = ({ children }) => {
  const [portalNode] = useState(() => {
    if (typeof document === 'undefined') {
      return null
    }
    const node = document.createElement('div')
    node.className = 'select-portal'
    return node
  })

  useEffect(() => {
    if (!portalNode) {
      return undefined
    }
    document.body.appendChild(portalNode)
    return () => {
      document.body.removeChild(portalNode)
    }
  }, [portalNode])

  if (!portalNode) {
    return null
  }

  return createPortal(children, portalNode)
}

export const SelectContent = ({ className, children }) => {
  const context = useContext(SelectContext)
  if (!context) {
    throw new Error('SelectContent must be used within Select')
  }

  const { open, setOpen, triggerRect } = context

  useEffect(() => {
    if (!open) {
      return undefined
    }
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        setOpen(false)
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [open, setOpen])

  if (!open) {
    return null
  }

  const style = triggerRect
    ? {
        position: 'absolute',
        top: triggerRect.top + triggerRect.height + 4,
        left: triggerRect.left,
        minWidth: triggerRect.width
      }
    : {}

  return (
    <SelectPortal>
      <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
      <div className="absolute z-50" style={style}>
        <div
          role="listbox"
          className={cn(
            'max-h-60 overflow-auto rounded-md border border-border bg-popover p-1 text-popover-foreground shadow-lg',
            className
          )}
        >
          {children}
        </div>
      </div>
    </SelectPortal>
  )
}

export const SelectItem = forwardRef(({ className, value, children, ...props }, ref) => {
  const context = useContext(SelectContext)
  if (!context) {
    throw new Error('SelectItem must be used within Select')
  }

  const { value: selected, select, registerItem } = context

  useEffect(() => {
    registerItem(value, typeof children === 'string' ? children : String(children))
  }, [value, children, registerItem])

  const handleSelect = () => {
    select(value)
  }

  const isSelected = selected === value

  return (
    <button
      type="button"
      role="option"
      aria-selected={isSelected}
      ref={ref}
      onClick={handleSelect}
      className={cn(
        'flex w-full cursor-pointer select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground',
        isSelected ? 'bg-accent text-accent-foreground' : 'text-foreground',
        className
      )}
      {...props}
    >
      {children}
    </button>
  )
})
SelectItem.displayName = 'SelectItem'
