import { Link, useParams } from 'react-router-dom'
import { PageHeader, Badge, MetricBlock, Skeleton, Button } from '../../components/ui/index.jsx'
import { HealthSummary, KeyFindings } from '../../components/domain/HealthSummary.jsx'
import { useRepo } from '../../hooks/useRepos.js'
import { useRepoScores } from '../../hooks/useRepoGraph.js'
import { useSelection } from '../../context/SelectionContext.jsx'
import { computeHealth } from '../../lib/health/computeHealth.js'
import { formatScore } from '../../lib/format/formatScore.js'
import '../../components/domain/domain.css'

export function OverviewPage() {
  const { repoId } = useParams()
  const { data: repo, isLoading } = useRepo(repoId)
  const { data: scoresData, isLoading: scoresLoading } = useRepoScores(repoId)
  const { setSelectedFilePath } = useSelection()

  const scores = scoresData?.scores ?? []
  const health = repo
    ? computeHealth({
        summary: repo.summary,
        statistics: repo.statistics,
        scores,
        cycleCount: repo.summary?.cycle_count,
      })
    : null

  const topFiles = scores.slice(0, 5)

  if (isLoading || scoresLoading) {
    return (
      <>
        <PageHeader title="Overview" subtitle="Where should I start?" />
        <Skeleton style={{ height: 200 }} />
      </>
    )
  }

  const name = repo?.repository?.name ?? 'Repository'
  const source = repo?.repository?.source

  return (
    <>
      <PageHeader title="Overview" subtitle="Where should I start in this codebase?" />

      <div className="overview-grid">
        <section>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
            <h2 style={{ fontSize: 'var(--text-lg)', fontWeight: 600 }}>{name}</h2>
            {source ? <Badge variant="muted">{source}</Badge> : null}
          </div>

          <div className="overview-stats">
            <MetricBlock label="Files" value={repo?.summary?.file_count ?? 0} />
            <MetricBlock label="Dependencies" value={repo?.summary?.edge_count ?? 0} />
            <MetricBlock label="Cycles" value={repo?.summary?.cycle_count ?? 0} />
            <MetricBlock
              label="Graph density"
              value={
                repo?.statistics?.graph_density != null
                  ? `${(repo.statistics.graph_density * 100).toFixed(1)}%`
                  : '—'
              }
            />
          </div>
        </section>

        <HealthSummary health={health} />
        <KeyFindings findings={health?.findings} />

        <section className="overview-files">
          <h2 style={{ fontSize: 'var(--text-lg)', fontWeight: 600 }}>Most critical files</h2>
          <ul className="overview-files__list">
            {topFiles.map((score) => (
              <li
                key={score.file_path}
                className="overview-files__item"
                onClick={() => setSelectedFilePath(score.file_path)}
              >
                <span className="overview-files__path mono">{score.file_path}</span>
                <span className="overview-files__score">{formatScore(score.criticality)}</span>
              </li>
            ))}
          </ul>
        </section>

        <div className="overview-actions">
          <Button as={Link} to="graph">
            Open dependency graph
          </Button>
          <Button as={Link} to="critical" variant="secondary">
            View all critical files
          </Button>
        </div>
      </div>
    </>
  )
}
