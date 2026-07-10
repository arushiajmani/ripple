import { Link, useParams } from 'react-router-dom'
import { AppShell } from '../components/layout/AppShell.jsx'
import { PageHeader, Button } from '../components/ui/index.jsx'
import { ProcessingView } from '../components/domain/ProcessingView.jsx'
import '../components/domain/domain.css'

export function ProcessingPage() {
  const { repoId } = useParams()

  return (
    <AppShell>
      <PageHeader title="Analyzing repository" subtitle={`Repository ${repoId}`} />
      <ProcessingView />
      <p style={{ marginTop: '2rem', textAlign: 'center' }}>
        <Button as={Link} to={`/repos/${repoId}/overview`} variant="secondary">
          Continue to workspace
        </Button>
      </p>
    </AppShell>
  )
}
