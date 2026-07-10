import { Progress } from '../ui/index.jsx'
import './domain.css'

const STAGES = [
  'Ingesting repository',
  'Parsing Python ASTs',
  'Building dependency graph',
  'Computing criticality scores',
]

export function ProcessingView({ stageIndex = 0 }) {
  return (
    <div className="processing">
      <Progress />
      <p className="processing__stage">{STAGES[stageIndex] ?? STAGES[0]}…</p>
      <p className="processing__hint">
        Analysis runs synchronously — large repositories may take a minute.
      </p>
    </div>
  )
}
