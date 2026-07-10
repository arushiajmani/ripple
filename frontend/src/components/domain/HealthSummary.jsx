import { healthLabel } from '../../lib/health/computeHealth.js'
import { Badge } from '../ui/index.jsx'
import './domain.css'

const VARIANT = {
  healthy: 'success',
  attention: 'warning',
  'at-risk': 'error',
}

export function HealthSummary({ health }) {
  if (!health) {
    return null
  }

  return (
    <div className="health-summary">
      <div className="health-summary__header">
        <h2 className="health-summary__title">Architecture health</h2>
        <Badge variant={VARIANT[health.overall] ?? 'default'}>
          {healthLabel(health.overall)}
        </Badge>
      </div>
    </div>
  )
}

export function KeyFindings({ findings }) {
  if (!findings?.length) {
    return null
  }

  return (
    <section className="key-findings">
      <h2 className="key-findings__title">Key findings</h2>
      <ul className="key-findings__list">
        {findings.map((item, index) => (
          <li key={index} className={`key-findings__item key-findings__item--${item.type}`}>
            {item.text}
          </li>
        ))}
      </ul>
    </section>
  )
}
