import { useNavigate, useParams } from 'react-router-dom'
import { PageHeader, Skeleton } from '../../components/ui/index.jsx'
import { CriticalFileRow } from '../../components/domain/CriticalFileRow.jsx'
import { useRepoScores } from '../../hooks/useRepoGraph.js'
import '../../components/domain/domain.css'

export function CriticalFilesPage() {
  const { repoId } = useParams()
  const navigate = useNavigate()
  const { data, isLoading } = useRepoScores(repoId)

  const scores = data?.scores ?? []

  function handleViewGraph(filePath) {
    navigate(`../graph?focus=${encodeURIComponent(filePath)}`)
  }

  if (isLoading) {
    return (
      <>
        <PageHeader title="Critical files" subtitle="Which files matter the most?" />
        <Skeleton style={{ height: 320 }} />
      </>
    )
  }

  return (
    <>
      <PageHeader title="Critical files" subtitle="Which files matter the most?" />

      <div className="critical-table-wrap">
        <table className="critical-table">
          <thead>
            <tr>
              <th>#</th>
              <th>File</th>
              <th>Criticality</th>
              <th>PageRank</th>
              <th>Betweenness</th>
              <th>Imported by</th>
              <th>Imports</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {scores.map((score, index) => (
              <CriticalFileRow
                key={score.file_path}
                score={score}
                rank={index + 1}
                onViewGraph={handleViewGraph}
              />
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
