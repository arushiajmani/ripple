import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Input } from '../ui/index.jsx'
import { useAnalyzeRepo } from '../../hooks/useAnalyzeRepo.js'
import { ApiError } from '../../api/client.js'
import './domain.css'

export function ImportForm() {
  const navigate = useNavigate()
  const analyze = useAnalyzeRepo()
  const [mode, setMode] = useState('github')
  const [githubUrl, setGithubUrl] = useState('')
  const [zipFile, setZipFile] = useState(null)
  const [error, setError] = useState(null)

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)

    const formData = new FormData()
    if (mode === 'github') {
      if (!githubUrl.trim()) {
        setError('Enter a GitHub repository URL.')
        return
      }
      formData.append('github_url', githubUrl.trim())
    } else {
      if (!zipFile) {
        setError('Choose a ZIP archive to upload.')
        return
      }
      formData.append('file', zipFile)
    }

    try {
      const result = await analyze.mutateAsync(formData)
      navigate(`/repos/${result.repo_id}/overview`, { replace: true })
    } catch (err) {
      const message =
        err instanceof ApiError ? err.detail : 'Analysis failed. Please try again.'
      setError(message)
    }
  }

  return (
    <form className="import-form" onSubmit={handleSubmit}>
      <div className="import-form__tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'github'}
          className={mode === 'github' ? 'import-form__tab--active' : 'import-form__tab'}
          onClick={() => setMode('github')}
        >
          GitHub URL
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'zip'}
          className={mode === 'zip' ? 'import-form__tab--active' : 'import-form__tab'}
          onClick={() => setMode('zip')}
        >
          ZIP upload
        </button>
      </div>

      {mode === 'github' ? (
        <label className="import-form__field">
          <span className="import-form__label">Repository URL</span>
          <Input
            type="url"
            placeholder="https://github.com/owner/repo"
            value={githubUrl}
            onChange={(e) => setGithubUrl(e.target.value)}
          />
        </label>
      ) : (
        <label className="import-form__field">
          <span className="import-form__label">ZIP archive</span>
          <Input
            type="file"
            accept=".zip,application/zip"
            onChange={(e) => setZipFile(e.target.files?.[0] ?? null)}
          />
        </label>
      )}

      {error ? (
        <p className="import-form__error" role="alert">
          {error}
        </p>
      ) : null}

      <Button type="submit" disabled={analyze.isPending}>
        {analyze.isPending ? 'Analyzing…' : 'Analyze repository'}
      </Button>
    </form>
  )
}
