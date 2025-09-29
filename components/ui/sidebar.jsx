import { forwardRef } from 'react'
import { cn } from './utils'

export const Sidebar = forwardRef(({ className, ...props }, ref) => (
  <aside
    ref={ref}
    className={cn('flex h-full w-64 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground', className)}
    {...props}
  />
))
Sidebar.displayName = 'Sidebar'

export const SidebarHeader = forwardRef(({ className, ...props }, ref) => (
  <div ref={ref} className={cn('border-b border-sidebar-border p-4', className)} {...props} />
))
SidebarHeader.displayName = 'SidebarHeader'

export const SidebarContent = forwardRef(({ className, ...props }, ref) => (
  <div ref={ref} className={cn('flex-1 overflow-y-auto p-4', className)} {...props} />
))
SidebarContent.displayName = 'SidebarContent'

export const SidebarFooter = forwardRef(({ className, ...props }, ref) => (
  <div ref={ref} className={cn('border-t border-sidebar-border p-4', className)} {...props} />
))
SidebarFooter.displayName = 'SidebarFooter'
