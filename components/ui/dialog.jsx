import {
  cloneElement,
  createContext,
  forwardRef,
  isValidElement,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState
} from 'react'
import { createPortal } from 'react-dom'
import { cn } from './utils'

const DialogContext = createContext(null)

export const Dialog = ({ open, defaultOpen = false, onOpenChange, children }) => {
  const isControlled = open !== undefined
  const [internalOpen, setInternalOpen] = useState(defaultOpen)

  useEffect(() => {
    if (isControlled) {
      setInternalOpen(Boolean(open))
    }
  }, [isControlled, open])

  const setOpen = useCallback(
    (nextOpen) => {
      if (!isControlled) {
        setInternalOpen(nextOpen)
      }
      onOpenChange?.(nextOpen)
    },
    [isControlled, onOpenChange]
  )

  const value = useMemo(
    () => ({
      open: internalOpen,
      setOpen
    }),
    [internalOpen, setOpen]
  )

  return <DialogContext.Provider value={value}>{children}</DialogContext.Provider>
}

export const DialogTrigger = ({ asChild = false, children }) => {
  const context = useContext(DialogContext)
  if (!context) {
    throw new Error('DialogTrigger must be used within Dialog')
  }

  const handleClick = (event) => {
    if (isValidElement(children)) {
      children.props?.onClick?.(event)
    }
    if (!event.defaultPrevented) {
      context.setOpen(true)
    }
  }

  if (asChild && isValidElement(children)) {
    return cloneElement(children, {
      onClick: handleClick
    })
  }

  return (
    <button type="button" onClick={handleClick}>
      {children}
    </button>
  )
}

const DialogPortal = ({ children }) => {
  const [portalNode] = useState(() => {
    if (typeof document === 'undefined') {
      return null
    }
    const node = document.createElement('div')
    node.className = 'dialog-portal'
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

export const DialogOverlay = forwardRef(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn('fixed inset-0 z-50 bg-background/80 backdrop-blur-sm', className)}
    {...props}
  />
))
DialogOverlay.displayName = 'DialogOverlay'

export const DialogContent = forwardRef(({ className, children, ...props }, ref) => {
  const context = useContext(DialogContext)
  if (!context) {
    throw new Error('DialogContent must be used within Dialog')
  }

  const { open, setOpen } = context

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

  const assignRef = (node) => {
    if (typeof ref === 'function') {
      ref(node)
    } else if (ref) {
      ref.current = node
    }
  }

  if (!open) {
    return null
  }

  const handleOverlayClick = () => setOpen(false)

  const content = (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <DialogOverlay onClick={handleOverlayClick} />
      <div
        role="dialog"
        aria-modal="true"
        ref={assignRef}
        className={cn(
          'relative z-50 w-full max-w-lg rounded-lg border border-border bg-background p-6 shadow-lg focus-visible:outline-none',
          className
        )}
        onClick={(event) => event.stopPropagation()}
        {...props}
      >
        {children}
      </div>
    </div>
  )

  return <DialogPortal>{content}</DialogPortal>
})
DialogContent.displayName = 'DialogContent'

export const DialogHeader = forwardRef(({ className, ...props }, ref) => (
  <div ref={ref} className={cn('flex flex-col space-y-1.5 text-center sm:text-left', className)} {...props} />
))
DialogHeader.displayName = 'DialogHeader'

export const DialogFooter = forwardRef(({ className, ...props }, ref) => (
  <div ref={ref} className={cn('flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2', className)} {...props} />
))
DialogFooter.displayName = 'DialogFooter'

export const DialogTitle = forwardRef(({ className, ...props }, ref) => (
  <h2 ref={ref} className={cn('text-lg font-semibold leading-none tracking-tight', className)} {...props} />
))
DialogTitle.displayName = 'DialogTitle'

export const DialogDescription = forwardRef(({ className, ...props }, ref) => (
  <p ref={ref} className={cn('text-sm text-muted-foreground', className)} {...props} />
))
DialogDescription.displayName = 'DialogDescription'
