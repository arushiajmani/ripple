import { Link } from 'react-router-dom'
import { Badge, Card } from '../ui/index.jsx'
import { formatRelativeTime } from '../../lib/format/formatDate.js'
import './domain.css'

export function RepoCard({ repo }) {
  const { repo_id, name, source, summary, analyzed_at } = repo

  return (
    <Card interactive className="repo-card">
      <Link to={`/repos/${repo_id}/overview`} className="repo-card__link">
        <div className="repo-card__header">
          <span className="repo-card__name">{name}</span>
          <Badge variant="muted">{source}</Badge>
        </div>
        <div className="repo-card__stats">
          <span>{summary?.file_count ?? 0} files</span>
          <span>·</span>
          <span>{summary?.edge_count ?? 0} dependencies</span>
          {summary?.cycle_count > 0 ? (
            <>
              <span>·</span>
              <span className="repo-card__warn">{summary.cycle_count} cycles</span>
            </>
          ) : null}
        </div>
        {analyzed_at ? (
          <span className="repo-card__time">Analyzed {formatRelativeTime(analyzed_at)}</span>
        ) : null}
      </Link>
    </Card>
  )
}
