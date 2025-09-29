import { cn } from './ui/utils'

const variantStyles = {
  error: 'bg-red-100 text-red-800 border border-red-200',
  success: 'bg-emerald-100 text-emerald-800 border border-emerald-200',
  warning: 'bg-amber-100 text-amber-900 border border-amber-200',
  info: 'bg-blue-50 text-blue-800 border border-blue-200'
}

export default function InlineNotice({ type = 'info', message, children, className }) {
  const content = message ?? children

  if (!content) {
    return null
  }

  const variantClass = variantStyles[type] ?? variantStyles.info

  return (
    <div className={cn('rounded-md px-4 py-3 text-sm font-medium', variantClass, className)}>
      {content}
    </div>
  )
}
