const API_BASE_URL = (
  import.meta.env.VITE_RAG_API_BASE_URL ||
  import.meta.env.VITE_EVALUATION_API_BASE_URL ||
  'http://localhost:8001'
).replace(/\/$/, '')

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  })

  const contentType = response.headers.get('content-type') || ''
  const body = contentType.includes('application/json')
    ? await response.json()
    : await response.text()

  if (!response.ok) {
    const detail = typeof body === 'object' ? body.detail : body
    throw new Error(detail || `요청 실패 (${response.status})`)
  }
  return body
}

export function getApiBaseUrl() {
  return API_BASE_URL
}

export function getBackendHealth() {
  return request('/api/health')
}


export function listEvaluationCases() {
  return request('/api/evaluation/cases')
}

export function runEvaluation(payload) {
  return request('/api/evaluation/run', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getEvaluationJob(jobId) {
  return request(`/api/evaluation/jobs/${encodeURIComponent(jobId)}`)
}

export function getEvaluationReport(jobId) {
  return request(`/api/evaluation/jobs/${encodeURIComponent(jobId)}/report`)
}

export function evaluationDownloadUrl(jobId, format) {
  return `${API_BASE_URL}/api/evaluation/jobs/${encodeURIComponent(jobId)}/download/${format}`
}
