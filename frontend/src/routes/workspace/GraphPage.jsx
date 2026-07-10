import { useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { PageHeader, Skeleton } from '../../components/ui/index.jsx'
import { GraphCanvas } from '../../components/domain/GraphCanvas.jsx'
import { GraphToolbar, GraphLegend } from '../../components/domain/GraphToolbar.jsx'
import { useRepoGraph } from '../../hooks/useRepoGraph.js'
import { useSelection } from '../../context/SelectionContext.jsx'
import '../../components/domain/domain.css'

export function GraphPage() {
  const { repoId } = useParams()
  const [searchParams] = useSearchParams()
  const focusFile = searchParams.get('focus')

  const { graph, scoresByPath, isLoading } = useRepoGraph(repoId)
  const { selectedFilePath, setSelectedFilePath } = useSelection()

  const [highlightMode, setHighlightMode] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [minCriticality, setMinCriticality] = useState(0)

  const nodeCount = graph?.nodes?.length ?? 0
  const showWarning = nodeCount > 200

  if (isLoading) {
    return (
      <>
        <PageHeader title="Dependency graph" subtitle="How is everything connected?" />
        <Skeleton style={{ height: 480 }} />
      </>
    )
  }

  return (
    <>
      <PageHeader title="Dependency graph" subtitle="How is everything connected?" />

      {showWarning ? (
        <p className="graph-warning" role="status">
          Large graph ({nodeCount} files) — use the criticality slider to reduce clutter.
        </p>
      ) : null}

      <div className="graph-page">
        <GraphToolbar
          highlightMode={highlightMode}
          onHighlightModeChange={setHighlightMode}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          minCriticality={minCriticality}
          onMinCriticalityChange={setMinCriticality}
          onFit={() => {}}
        />

        <GraphCanvas
          graph={graph}
          scoresByPath={scoresByPath}
          selectedFilePath={selectedFilePath}
          onSelectNode={setSelectedFilePath}
          highlightMode={highlightMode}
          searchQuery={searchQuery}
          minCriticality={minCriticality}
          focusFile={focusFile}
        />

        <GraphLegend />
      </div>
    </>
  )
}
