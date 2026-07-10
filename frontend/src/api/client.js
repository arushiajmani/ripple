const API_BASE = import.meta.env.VITE_API_URL ?? ''

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function parseError(response) {
  try {
    const body = await response.json()
    if (typeof body?.detail === 'string') {
      return body.detail
    }
  } catch {
    // ignore
  }
  return response.statusText || 'Request failed'
}

export async function apiFetch(path, options = {}) {
  const url = `${API_BASE}${path}`
  const response = await fetch(url, options)

  if (!response.ok) {
    const detail = await parseError(response)
    throw new ApiError(response.status, detail)
  }

  if (response.status === 204) {
    return null
  }

  return response.json()
}

export async function apiPostForm(path, formData) {
  return apiFetch(path, {
    method: 'POST',
    body: formData,
  })
}
