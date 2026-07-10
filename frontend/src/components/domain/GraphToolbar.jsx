import { Button, Input } from '../ui/index.jsx'
import { Maximize2 } from 'lucide-react'
import './domain.css'

export function GraphToolbar({
  highlightMode,
  onHighlightModeChange,
  searchQuery,
  onSearchChange,
  minCriticality,
  onMinCriticalityChange,
  onFit,
}) {
  return (
    <div className="graph-toolbar">
      <Input
        className="graph-toolbar__search"
        placeholder="Filter files…"
        value={searchQuery}
        onChange={(e) => onSearchChange(e.target.value)}
        aria-label="Filter graph nodes"
      />

      <div className="graph-toolbar__group">
        <Button
          variant={highlightMode === 'dependents' ? 'primary' : 'secondary'}
          size="sm"
          onClick={() =>
            onHighlightModeChange(highlightMode === 'dependents' ? null : 'dependents')
          }
        >
          Dependents
        </Button>
        <Button
          variant={highlightMode === 'dependencies' ? 'primary' : 'secondary'}
          size="sm"
          onClick={() =>
            onHighlightModeChange(highlightMode === 'dependencies' ? null : 'dependencies')
          }
        >
          Dependencies
        </Button>
        <Button
          variant={highlightMode === 'focus' ? 'primary' : 'secondary'}
          size="sm"
          onClick={() => onHighlightModeChange(highlightMode === 'focus' ? null : 'focus')}
        >
          Focus
        </Button>
      </div>

      <label className="graph-toolbar__slider">
        <span>Min criticality</span>
        <input
          type="range"
          min={0}
          max={0.8}
          step={0.05}
          value={minCriticality}
          onChange={(e) => onMinCriticalityChange(Number(e.target.value))}
        />
      </label>

      <div className="graph-toolbar__zoom">
        <Button variant="ghost" size="sm" onClick={onFit} aria-label="Fit to screen">
          <Maximize2 size={16} />
        </Button>
      </div>
    </div>
  )
}

export function GraphLegend() {
  return (
    <div className="graph-legend">
      <span className="graph-legend__item">
        <span className="graph-legend__dot graph-legend__dot--low" /> Low risk
      </span>
      <span className="graph-legend__item">
        <span className="graph-legend__dot graph-legend__dot--med" /> Medium
      </span>
      <span className="graph-legend__item">
        <span className="graph-legend__dot graph-legend__dot--high" /> High
      </span>
      <span className="graph-legend__hint">Size = criticality · Arrow = imports</span>
    </div>
  )
}
