import React from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';

/**
 * EmptyState - Placeholder for empty lists/pages
 *
 * Usage:
 * <EmptyState
 *   icon={Bot}
 *   title="No bots yet"
 *   description="Add your first bot to get started"
 *   action={{ label: "Add Bot", onClick: handleAdd }}
 * />
 */

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
  ...props
}) {
  return (
    <Card className={cn('border-dashed', className)} {...props}>
      <CardContent className="flex flex-col items-center justify-center text-center py-12 px-6">
        {Icon && (
          <div className="rounded-full bg-muted p-4 mb-4">
            <Icon className="h-8 w-8 text-muted-foreground" />
          </div>
        )}

        {title && (
          <h3 className="text-lg font-semibold mb-2">
            {title}
          </h3>
        )}

        {description && (
          <p className="text-sm text-muted-foreground mb-6 max-w-sm">
            {description}
          </p>
        )}

        {action && (
          <Button onClick={action.onClick} variant={action.variant || 'default'}>
            {action.label}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * EmptySearchResults - Empty state specifically for search results
 */
export function EmptySearchResults({ searchTerm, onClear }) {
  return (
    <div className="text-center py-12">
      <p className="text-sm text-muted-foreground mb-2">
        No results found for <strong>"{searchTerm}"</strong>
      </p>
      <Button variant="ghost" size="sm" onClick={onClear}>
        Clear search
      </Button>
    </div>
  );
}

export default EmptyState;
