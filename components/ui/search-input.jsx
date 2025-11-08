import React from 'react';
import { Search, X } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

/**
 * SearchInput - Debounced search input with clear button
 *
 * Usage:
 * <SearchInput
 *   value={search}
 *   onChange={setSearch}
 *   placeholder="Search bots..."
 *   debounce={300}
 * />
 */

export const SearchInput = React.forwardRef(
  (
    {
      value,
      onChange,
      onClear,
      placeholder = 'Search...',
      debounce = 300,
      className,
      ...props
    },
    ref
  ) => {
    const [localValue, setLocalValue] = React.useState(value || '');
    const debounceTimeout = React.useRef(null);

    // Sync external value changes
    React.useEffect(() => {
      setLocalValue(value || '');
    }, [value]);

    // Debounced onChange
    const handleChange = (e) => {
      const newValue = e.target.value;
      setLocalValue(newValue);

      if (debounceTimeout.current) {
        clearTimeout(debounceTimeout.current);
      }

      debounceTimeout.current = setTimeout(() => {
        onChange?.(newValue);
      }, debounce);
    };

    // Clear search
    const handleClear = () => {
      setLocalValue('');
      onChange?.('');
      onClear?.();
    };

    // Cleanup on unmount
    React.useEffect(() => {
      return () => {
        if (debounceTimeout.current) {
          clearTimeout(debounceTimeout.current);
        }
      };
    }, []);

    return (
      <div className={cn('relative flex items-center', className)}>
        <Search className="absolute left-3 h-4 w-4 text-muted-foreground pointer-events-none" />
        <Input
          ref={ref}
          type="text"
          value={localValue}
          onChange={handleChange}
          placeholder={placeholder}
          className="pl-9 pr-9"
          {...props}
        />
        {localValue && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={handleClear}
            className="absolute right-1 h-7 w-7 p-0 hover:bg-transparent"
          >
            <X className="h-4 w-4" />
            <span className="sr-only">Clear search</span>
          </Button>
        )}
      </div>
    );
  }
);

SearchInput.displayName = 'SearchInput';

export default SearchInput;
