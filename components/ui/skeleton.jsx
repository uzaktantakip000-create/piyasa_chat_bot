import React from 'react';
import { cn } from '@/lib/utils';

/**
 * Skeleton - Loading placeholder component
 *
 * Usage:
 * <Skeleton className="h-12 w-12 rounded-full" />
 * <Skeleton className="h-4 w-[250px]" />
 */

export function Skeleton({ className, ...props }) {
  return (
    <div
      className={cn('animate-pulse rounded-md bg-muted', className)}
      {...props}
    />
  );
}

/**
 * SkeletonCard - Preset skeleton for card layouts
 */
export function SkeletonCard({ className, ...props }) {
  return (
    <div className={cn('rounded-lg border p-4 space-y-3', className)} {...props}>
      <Skeleton className="h-5 w-2/5" />
      <Skeleton className="h-4 w-4/5" />
      <Skeleton className="h-4 w-3/5" />
    </div>
  );
}

/**
 * SkeletonTable - Preset skeleton for table rows
 */
export function SkeletonTable({ rows = 5, cols = 4, className, ...props }) {
  return (
    <div className={cn('space-y-2', className)} {...props}>
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div key={rowIndex} className="flex gap-4">
          {Array.from({ length: cols }).map((_, colIndex) => (
            <Skeleton key={colIndex} className="h-10 flex-1" />
          ))}
        </div>
      ))}
    </div>
  );
}

/**
 * SkeletonList - Preset skeleton for list items
 */
export function SkeletonList({ items = 5, className, ...props }) {
  return (
    <div className={cn('space-y-3', className)} {...props}>
      {Array.from({ length: items }).map((_, index) => (
        <div key={index} className="flex items-center gap-4">
          <Skeleton className="h-12 w-12 rounded-full" />
          <div className="space-y-2 flex-1">
            <Skeleton className="h-4 w-[250px]" />
            <Skeleton className="h-4 w-[200px]" />
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * SkeletonText - Preset skeleton for text paragraphs
 */
export function SkeletonText({ lines = 3, className, ...props }) {
  return (
    <div className={cn('space-y-2', className)} {...props}>
      {Array.from({ length: lines }).map((_, index) => (
        <Skeleton
          key={index}
          className={cn(
            'h-4',
            index === lines - 1 ? 'w-4/5' : 'w-full' // Last line shorter
          )}
        />
      ))}
    </div>
  );
}

/**
 * SkeletonForm - Preset skeleton for form fields
 */
export function SkeletonForm({ fields = 3, className, ...props }) {
  return (
    <div className={cn('space-y-4', className)} {...props}>
      {Array.from({ length: fields }).map((_, index) => (
        <div key={index} className="space-y-2">
          <Skeleton className="h-4 w-24" /> {/* Label */}
          <Skeleton className="h-10 w-full" /> {/* Input */}
        </div>
      ))}
    </div>
  );
}

/**
 * SkeletonAvatar - Preset skeleton for avatar
 */
export function SkeletonAvatar({ size = 'md', className, ...props }) {
  const sizeClasses = {
    sm: 'h-8 w-8',
    md: 'h-12 w-12',
    lg: 'h-16 w-16',
    xl: 'h-24 w-24',
  };

  return (
    <Skeleton
      className={cn('rounded-full', sizeClasses[size], className)}
      {...props}
    />
  );
}

/**
 * SkeletonButton - Preset skeleton for buttons
 */
export function SkeletonButton({ size = 'md', className, ...props }) {
  const sizeClasses = {
    sm: 'h-8 w-20',
    md: 'h-10 w-24',
    lg: 'h-12 w-28',
  };

  return (
    <Skeleton
      className={cn('rounded-md', sizeClasses[size], className)}
      {...props}
    />
  );
}

/**
 * SkeletonBadge - Preset skeleton for badges
 */
export function SkeletonBadge({ className, ...props }) {
  return (
    <Skeleton
      className={cn('h-5 w-16 rounded-full', className)}
      {...props}
    />
  );
}

/**
 * SkeletonMetricCard - Preset skeleton for dashboard metric cards
 */
export function SkeletonMetricCard({ className, ...props }) {
  return (
    <div className={cn('rounded-lg border p-6 space-y-3', className)} {...props}>
      <div className="flex items-center justify-between">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-4 w-4 rounded" />
      </div>
      <Skeleton className="h-8 w-32" />
      <Skeleton className="h-3 w-full" />
    </div>
  );
}

/**
 * SkeletonDashboard - Preset skeleton for full dashboard layout
 */
export function SkeletonDashboard({ className, ...props }) {
  return (
    <div className={cn('space-y-6', className)} {...props}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <Skeleton className="h-8 w-48" />
        <div className="flex gap-2">
          <SkeletonButton />
          <SkeletonButton />
        </div>
      </div>

      {/* Metric cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <SkeletonMetricCard key={index} />
        ))}
      </div>

      {/* Content */}
      <SkeletonCard className="p-6 h-64" />
    </div>
  );
}

// Export all components
export default {
  Skeleton,
  SkeletonCard,
  SkeletonTable,
  SkeletonList,
  SkeletonText,
  SkeletonForm,
  SkeletonAvatar,
  SkeletonButton,
  SkeletonBadge,
  SkeletonMetricCard,
  SkeletonDashboard,
};
