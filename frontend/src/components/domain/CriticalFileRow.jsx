import { useSelection } from '../../context/SelectionContext.jsx'
import { criticalityBand } from '../../lib/health/computeHealth.js'
import { formatScore } from '../../lib/format/formatScore.js'
import { Button } from '../ui/index.jsx'
import './domain.css'

export function CriticalFileRow({ score, rank, onViewGraph }) {
  const { setSelectedFilePath } = useSelection()
  const band = criticalityBand(score.criticality)

  return (
    <tr
      className="critical-row"
      onClick={() => setSelectedFilePath(score.file_path)}
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && setSelectedFilePath(score.file_path)}
    >
      <td className="critical-row__rank">{rank}</td>
      <td className="critical-row__path mono" title={score.file_path}>
        {score.file_path}
      </td>
      <td>
        <div className="critical-row__bar-wrap">
          <div
            className={`critical-row__bar critical-row__bar--${band}`}
            style={{ width: `${Math.max(score.criticality * 100, 4)}%` }}
          />
          <span className="critical-row__score">{formatScore(score.criticality)}</span>
        </div>
      </td>
      <td className="critical-row__num">{formatScore(score.pagerank)}</td>
      <td className="critical-row__num">{formatScore(score.betweenness)}</td>
      <td className="critical-row__num">{score.in_degree}</td>
      <td className="critical-row__num">{score.out_degree}</td>
      <td>
        <Button
          variant="ghost"
          size="sm"
          onClick={(e) => {
            e.stopPropagation()
            onViewGraph?.(score.file_path)
          }}
        >
          Graph
        </Button>
      </td>
    </tr>
  )
}
