import { Button } from '@/components/ui/button';
import { LayoutGrid, Rows3 } from 'lucide-react';

function noop() {}

export default function ViewModeToggle({
  mode,
  onChange = noop,
  cardsLabel = 'Kartlar',
  tableLabel = 'Tablo',
  size = 'sm',
  className = '',
  ariaLabel = 'Görünüm modu'
}) {
  const isCards = mode === 'cards';
  const isTable = mode === 'table';

  const handleChange = (nextMode) => {
    if (nextMode === mode) {
      return;
    }
    onChange(nextMode);
  };

  return (
    <div
      className={`inline-flex overflow-hidden rounded-md border border-border bg-muted/30 shadow-sm ${className}`.trim()}
      role="group"
      aria-label={ariaLabel}
    >
      <Button
        type="button"
        variant={isCards ? 'default' : 'ghost'}
        size={size}
        className="gap-1 rounded-r-none"
        onClick={() => handleChange('cards')}
        aria-pressed={isCards}
      >
        <LayoutGrid className="h-4 w-4" aria-hidden="true" />
        <span>{cardsLabel}</span>
      </Button>
      <Button
        type="button"
        variant={isTable ? 'default' : 'ghost'}
        size={size}
        className="gap-1 rounded-l-none border-l border-border"
        onClick={() => handleChange('table')}
        aria-pressed={isTable}
      >
        <Rows3 className="h-4 w-4" aria-hidden="true" />
        <span>{tableLabel}</span>
      </Button>
    </div>
  );
}
