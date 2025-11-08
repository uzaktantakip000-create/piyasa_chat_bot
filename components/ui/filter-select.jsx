import React from 'react';
import { Filter } from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

/**
 * FilterSelect - Dropdown filter with visual indicator
 *
 * Usage:
 * <FilterSelect
 *   value={filter}
 *   onValueChange={setFilter}
 *   options={[
 *     { value: 'all', label: 'All' },
 *     { value: 'active', label: 'Active', count: 10 },
 *     { value: 'inactive', label: 'Inactive', count: 5 },
 *   ]}
 * />
 */

export const FilterSelect = React.forwardRef(
  (
    {
      value,
      onValueChange,
      options = [],
      placeholder = 'Filter...',
      showIcon = true,
      showCount = true,
      className,
      ...props
    },
    ref
  ) => {
    const activeOption = options.find((opt) => opt.value === value);
    const hasActiveFilter = value && value !== 'all';

    return (
      <div className={cn('flex items-center gap-2', className)}>
        {showIcon && hasActiveFilter && (
          <Filter className="h-4 w-4 text-primary" />
        )}
        <Select value={value} onValueChange={onValueChange} {...props}>
          <SelectTrigger
            ref={ref}
            className={cn(
              'w-[180px]',
              hasActiveFilter && 'border-primary'
            )}
          >
            <SelectValue placeholder={placeholder} />
          </SelectTrigger>
          <SelectContent>
            {options.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                <div className="flex items-center justify-between w-full gap-4">
                  <span>{option.label}</span>
                  {showCount && option.count !== undefined && (
                    <Badge variant="secondary" className="ml-auto">
                      {option.count}
                    </Badge>
                  )}
                </div>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    );
  }
);

FilterSelect.displayName = 'FilterSelect';

/**
 * FilterBar - Combined search and filter controls
 *
 * Usage:
 * <FilterBar
 *   searchValue={search}
 *   onSearchChange={setSearch}
 *   filterValue={filter}
 *   onFilterChange={setFilter}
 *   filterOptions={[...]}
 * />
 */
export const FilterBar = React.forwardRef(
  (
    {
      searchValue,
      onSearchChange,
      searchPlaceholder,
      filterValue,
      onFilterChange,
      filterOptions,
      filterPlaceholder,
      className,
      children,
      ...props
    },
    ref
  ) => {
    // Import SearchInput here to avoid circular deps
    const SearchInput = require('./search-input').SearchInput;

    return (
      <div
        ref={ref}
        className={cn(
          'flex flex-col sm:flex-row gap-3 items-start sm:items-center',
          className
        )}
        {...props}
      >
        {/* Search */}
        {onSearchChange && (
          <SearchInput
            value={searchValue}
            onChange={onSearchChange}
            placeholder={searchPlaceholder}
            className="w-full sm:w-auto sm:flex-1 sm:max-w-sm"
          />
        )}

        {/* Filter */}
        {filterOptions && onFilterChange && (
          <FilterSelect
            value={filterValue}
            onValueChange={onFilterChange}
            options={filterOptions}
            placeholder={filterPlaceholder}
          />
        )}

        {/* Additional controls */}
        {children && (
          <div className="flex items-center gap-2 ml-auto">
            {children}
          </div>
        )}
      </div>
    );
  }
);

FilterBar.displayName = 'FilterBar';

export default FilterSelect;
