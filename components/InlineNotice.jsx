import { Link } from 'react-router-dom'

import { cn } from './ui/utils'

const variantStyles = {
  error: 'bg-red-100 text-red-800 border border-red-200',
  success: 'bg-emerald-100 text-emerald-800 border border-emerald-200',
  warning: 'bg-amber-100 text-amber-900 border border-amber-200',
  info: 'bg-blue-50 text-blue-800 border border-blue-200'
}

export default function InlineNotice({
  type = 'info',
  message,
  children,
  className,
  withSupportLinks,
  supportHref = '/help',
  supportLabel = 'Destek rehberini aç',
  contactHref = 'mailto:destek@piyasa-sim.dev',
  contactLabel = 'destek ekibiyle iletişime geç'
}) {
  const content = message ?? children

  if (!content) {
    return null
  }

  const variantClass = variantStyles[type] ?? variantStyles.info
  const showSupport = withSupportLinks ?? type === 'error'

  return (
    <div className={cn('rounded-md px-4 py-3 text-sm font-medium space-y-2', variantClass, className)}>
      <div>{content}</div>
      {showSupport ? (
        <div className="flex flex-wrap items-center gap-2 text-xs font-normal">
          <Link className="underline underline-offset-2" to={supportHref}>
            {supportLabel}
          </Link>
          <span aria-hidden="true">•</span>
          <a className="underline underline-offset-2" href={contactHref} target="_blank" rel="noreferrer">
            {contactLabel}
          </a>
        </div>
      ) : null}
    </div>
  )
}
