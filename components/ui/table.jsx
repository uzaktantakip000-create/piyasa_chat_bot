import { forwardRef } from 'react'
import { cn } from './utils'

export const Table = forwardRef(({ className, ...props }, ref) => (
  <table ref={ref} className={cn('w-full caption-bottom text-sm', className)} {...props} />
))
Table.displayName = 'Table'

export const TableHeader = forwardRef(({ className, ...props }, ref) => (
  <thead ref={ref} className={cn('[&_tr]:border-b', className)} {...props} />
))
TableHeader.displayName = 'TableHeader'

export const TableBody = forwardRef(({ className, ...props }, ref) => (
  <tbody ref={ref} className={cn('[&_tr:last-child]:border-0', className)} {...props} />
))
TableBody.displayName = 'TableBody'

export const TableFooter = forwardRef(({ className, ...props }, ref) => (
  <tfoot
    ref={ref}
    className={cn('bg-muted font-medium text-foreground', className)}
    {...props}
  />
))
TableFooter.displayName = 'TableFooter'

export const TableRow = forwardRef(({ className, ...props }, ref) => (
  <tr
    ref={ref}
    className={cn('border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted', className)}
    {...props}
  />
))
TableRow.displayName = 'TableRow'

export const TableHead = forwardRef(({ className, ...props }, ref) => (
  <th
    ref={ref}
    className={cn('h-12 px-4 text-left align-middle font-medium text-muted-foreground', className)}
    {...props}
  />
))
TableHead.displayName = 'TableHead'

export const TableCell = forwardRef(({ className, ...props }, ref) => (
  <td ref={ref} className={cn('p-4 align-middle', className)} {...props} />
))
TableCell.displayName = 'TableCell'

export const TableCaption = forwardRef(({ className, ...props }, ref) => (
  <caption ref={ref} className={cn('mt-4 text-sm text-muted-foreground', className)} {...props} />
))
TableCaption.displayName = 'TableCaption'
