import { useSelection } from '../../context/SelectionContext.jsx'
import { criticalityLabel } from '../../lib/health/computeHealth.js'
import { formatScore } from '../../lib/format/formatScore.js'
import { useRepoGraph } from '../../hooks/useRepoGraph.js'
import { getNeighbors } from '../../lib/graph/buildCyElements.js'
import { MetricBlock } from '../ui/index.jsx'
import { X } from 'lucide-react'
import './domain.css'

export function FileDetailPanel({ repoId }) {
  const { selectedFilePath, setSelectedFilePath } = useSelection()
  const { graph, scores, scoresByPath } = useRepoGraph(repoId)

  if (!selectedFilePath) {
    return null
  }

  const score = scoresByPath[selectedFilePath]
  const rank = scores.findIndex((s) => s.file_path === selectedFilePath) + 1
  const edges = graph?.edges ?? []
  const dependencies = getNeighbors(edges, selectedFilePath, 'dependencies')
  const dependents = getNeighbors(edges, selectedFilePath, 'dependents')

  const importance = score
    ? `Ranked #${rank} by criticality. Imported by ${score.in_degree} file${score.in_degree === 1 ? '' : 's'} directly. ${criticalityLabel(score.criticality)}.`
    : 'This file is in the dependency graph but has no computed score.'

  return (
    <aside
      className="file-panel"
      role="complementary"
      aria-label="File details"
      aria-live="polite"
    >
      <header className="file-panel__header">
        <h2 className="file-panel__title">File details</h2>
        <button
          type="button"
          className="file-panel__close"
          onClick={() => setSelectedFilePath(null)}
          aria-label="Close panel"
        >
          <X size={18} />
        </button>
      </header>

      <p className="file-panel__path mono">{selectedFilePath}</p>

      <section className="file-panel__section">
        <h3>Why this matters</h3>
        <p className="file-panel__prose">{importance}</p>
      </section>

      {score ? (
        <section className="file-panel__metrics">
          <MetricBlock label="Criticality" value={formatScore(score.criticality)} />
          <MetricBlock label="PageRank" value={formatScore(score.pagerank)} />
          <MetricBlock label="Betweenness" value={formatScore(score.betweenness)} />
          <MetricBlock
            label="Degree"
            value={`${score.in_degree} in · ${score.out_degree} out`}
          />
        </section>
      ) : null}

      <section className="file-panel__section">
        <h3>Dependencies ({dependencies.length})</h3>
        <ul className="file-panel__list">
          {dependencies.length ? (
            dependencies.map((path) => (
              <li key={path}>
                <button
                  type="button"
                  className="file-panel__link"
                  onClick={() => setSelectedFilePath(path)}
                >
                  {path}
                </button>
              </li>
            ))
          ) : (
            <li className="file-panel__muted">No in-repo imports</li>
          )}
        </ul>
      </section>

      <section className="file-panel__section">
        <h3>Dependents ({dependents.length})</h3>
        <ul className="file-panel__list">
          {dependents.length ? (
            dependents.map((path) => (
              <li key={path}>
                <button
                  type="button"
                  className="file-panel__link"
                  onClick={() => setSelectedFilePath(path)}
                >
                  {path}
                </button>
              </li>
            ))
          ) : (
            <li className="file-panel__muted">Nothing imports this file</li>
          )}
        </ul>
      </section>
    </aside>
  )
}
