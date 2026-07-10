import { Link } from 'react-router-dom'
import { FolderGit2 } from 'lucide-react'
import { AppShell } from '../components/layout/AppShell.jsx'
import { Button, EmptyState, Skeleton } from '../components/ui/index.jsx'
import { RepoCard } from '../components/domain/RepoCard.jsx'
import { useRepos } from '../hooks/useRepos.js'
import '../components/domain/domain.css'

export function LandingPage() {
  const { data: repos, isLoading } = useRepos()

  return (
    <AppShell>
      <section className="landing-hero">
        <h1 className="landing-hero__title">Understand unfamiliar codebases</h1>
        <p className="landing-hero__desc">
          Ripple analyzes Python repositories — building dependency graphs, scoring
          architectural criticality, and surfacing what breaks when you change a file.
        </p>
        <Button as={Link} to="/import">
          Analyze a repository
        </Button>
      </section>

      <section>
        <h2 className="landing-repos__title">Recent repositories</h2>
        {isLoading ? (
          <div className="landing-repos">
            <Skeleton style={{ height: 100 }} />
            <Skeleton style={{ height: 100 }} />
          </div>
        ) : repos?.length ? (
          <div className="landing-repos">
            {repos.map((repo) => (
              <RepoCard key={repo.repo_id} repo={repo} />
            ))}
          </div>
        ) : (
          <EmptyState
            icon={FolderGit2}
            title="No repositories yet"
            description="Import a GitHub repository or ZIP archive to start exploring."
            action={
              <Button as={Link} to="/import">
                Analyze your first repo
              </Button>
            }
          />
        )}
      </section>
    </AppShell>
  )
}
