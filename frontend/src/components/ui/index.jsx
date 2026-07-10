import clsx from 'clsx'
import './ui.css'

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  className,
  as: Component = 'button',
  ...props
}) {
  return (
    <Component
      className={clsx('ui-btn', `ui-btn--${variant}`, `ui-btn--${size}`, className)}
      {...props}
    >
      {children}
    </Component>
  )
}

export function Card({ children, className, interactive, ...props }) {
  return (
    <div
      className={clsx('ui-card', interactive && 'ui-card--interactive', className)}
      {...props}
    >
      {children}
    </div>
  )
}

export function Badge({ children, variant = 'default', className }) {
  return (
    <span className={clsx('ui-badge', `ui-badge--${variant}`, className)}>
      {children}
    </span>
  )
}

export function MetricBlock({ label, value, hint, className }) {
  return (
    <div className={clsx('ui-metric', className)}>
      <span className="ui-metric__label">{label}</span>
      <span className="ui-metric__value">{value}</span>
      {hint ? <span className="ui-metric__hint">{hint}</span> : null}
    </div>
  )
}

export function Input({ className, ...props }) {
  return <input className={clsx('ui-input', className)} {...props} />
}

export function Skeleton({ className, style }) {
  return <div className={clsx('ui-skeleton', className)} style={style} aria-hidden="true" />
}

export function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="ui-empty">
      {Icon ? <Icon className="ui-empty__icon" size={32} strokeWidth={1.5} /> : null}
      <h3 className="ui-empty__title">{title}</h3>
      {description ? <p className="ui-empty__desc">{description}</p> : null}
      {action}
    </div>
  )
}

export function Progress({ className }) {
  return (
    <div className={clsx('ui-progress', className)} role="progressbar" aria-label="Loading">
      <div className="ui-progress__bar" />
    </div>
  )
}

export function PageHeader({ title, subtitle }) {
  return (
    <header className="ui-page-header">
      <h1 className="ui-page-header__title">{title}</h1>
      {subtitle ? <p className="ui-page-header__subtitle">{subtitle}</p> : null}
    </header>
  )
}
