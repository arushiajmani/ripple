import { NavLink, Link, Outlet, useParams } from 'react-router-dom'
import {
  LayoutDashboard,
  GitBranch,
  Star,
  AlertCircle,
  FolderTree,
  BarChart3,
  Settings,
  Target,
} from 'lucide-react'
import clsx from 'clsx'
import { useRepo } from '../../hooks/useRepos.js'
import { SelectionProvider } from '../../context/SelectionContext.jsx'
import { FileDetailPanel } from '../domain/FileDetailPanel.jsx'
import { formatRelativeTime } from '../../lib/format/formatDate.js'
import './layout.css'

const NAV_ITEMS = [
  { to: 'overview', label: 'Overview', icon: LayoutDashboard, enabled: true },
  { to: 'architecture', label: 'Architecture', icon: BarChart3, enabled: false },
  { to: 'graph', label: 'Dependency Graph', icon: GitBranch, enabled: true },
  { to: 'critical', label: 'Critical Files', icon: Star, enabled: true },
  { to: 'impact', label: 'Impact Analysis', icon: Target, enabled: false },
  { to: 'cycles', label: 'Cycles', icon: AlertCircle, enabled: false },
  { to: 'explorer', label: 'Repository Explorer', icon: FolderTree, enabled: false },
  { to: 'settings', label: 'Settings', icon: Settings, enabled: false },
]

export function WorkspaceShell() {
  const { repoId } = useParams()
  const { data: repo } = useRepo(repoId)

  const name =
    repo?.repository?.owner && repo?.repository?.repo_name
      ? `${repo.repository.owner}/${repo.repository.repo_name}`
      : repo?.repository?.name ?? 'Repository'

  const fileCount = repo?.summary?.file_count
  const analyzedAt = repo?.analyzed_at

  return (
    <SelectionProvider>
      <div className="workspace">
        <aside className="workspace__sidebar">
          <Link to="/" className="workspace__brand">
            Ripple
          </Link>
          <nav className="workspace__nav" aria-label="Workspace">
            {NAV_ITEMS.map(({ to, label, icon: Icon, enabled }) => (
              <NavLink
                key={to}
                to={enabled ? to : '#'}
                className={({ isActive }) =>
                  clsx(
                    'workspace__nav-link',
                    isActive && enabled && 'workspace__nav-link--active',
                    !enabled && 'workspace__nav-link--disabled',
                  )
                }
                aria-disabled={!enabled}
                tabIndex={enabled ? 0 : -1}
              >
                <Icon size={16} strokeWidth={1.75} />
                {label}
              </NavLink>
            ))}
          </nav>
        </aside>

        <div className="workspace__body">
          <header className="workspace__header">
            <div className="workspace__header-left">
              <Link to="/" className="workspace__back">
                ← Repos
              </Link>
              <span className="workspace__repo-name">{name}</span>
              {fileCount != null ? (
                <span className="workspace__meta">
                  {fileCount} files
                  {analyzedAt ? ` · analyzed ${formatRelativeTime(analyzedAt)}` : ''}
                </span>
              ) : null}
            </div>
          </header>

          <main className="workspace__content">
            <Outlet />
          </main>
        </div>

        <FileDetailPanel repoId={repoId} />
      </div>
    </SelectionProvider>
  )
}
