import { AppShell } from '../components/layout/AppShell.jsx'
import { PageHeader } from '../components/ui/index.jsx'
import { ImportForm } from '../components/domain/ImportForm.jsx'
import '../components/domain/domain.css'

export function ImportPage() {
  return (
    <AppShell>
      <PageHeader
        title="Import repository"
        subtitle="Analyze a public GitHub repository or upload a ZIP archive."
      />
      <ImportForm />
    </AppShell>
  )
}
