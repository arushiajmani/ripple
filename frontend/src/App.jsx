import { Navigate, Route, Routes } from 'react-router-dom'
import { LandingPage } from './routes/LandingPage.jsx'
import { ImportPage } from './routes/ImportPage.jsx'
import { ProcessingPage } from './routes/ProcessingPage.jsx'
import { WorkspaceShell } from './components/layout/WorkspaceShell.jsx'
import { OverviewPage } from './routes/workspace/OverviewPage.jsx'
import { GraphPage } from './routes/workspace/GraphPage.jsx'
import { CriticalFilesPage } from './routes/workspace/CriticalFilesPage.jsx'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/import" element={<ImportPage />} />
      <Route path="/processing/:repoId" element={<ProcessingPage />} />
      <Route path="/repos/:repoId" element={<WorkspaceShell />}>
        <Route index element={<Navigate to="overview" replace />} />
        <Route path="overview" element={<OverviewPage />} />
        <Route path="graph" element={<GraphPage />} />
        <Route path="critical" element={<CriticalFilesPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
