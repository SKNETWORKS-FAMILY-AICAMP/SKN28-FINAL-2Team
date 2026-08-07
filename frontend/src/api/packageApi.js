const API_BASE_URL = 'http://localhost:8000'

const getAccessToken = () => localStorage.getItem('accessToken')

const authHeaders = () => {
  const accessToken = getAccessToken()

  const headers = {
    'Content-Type': 'application/json',
  }

  if (
    accessToken &&
    accessToken !== 'null' &&
    accessToken !== 'undefined'
  ) {
    headers.Authorization = `Bearer ${accessToken}`
  }

  return headers
}

const parseError = async (response, fallbackMessage) => {
  try {
    const data = await response.json()

    if (data.detail) {
      return data.detail
    }
  } catch {
    // 응답 본문이 없는 경우 기본 메시지 사용
  }

  return fallbackMessage
}

export async function getPackages(params = {}) {
  const query = new URLSearchParams()

  if (params.category) {
    query.set('category', params.category)
  }

  if (params.style) {
    query.set('style', params.style)
  }

  if (params.durationDays) {
    query.set('duration_days', params.durationDays)
  }

  if (params.maxPrice) {
    query.set('max_price', params.maxPrice)
  }

  const queryString = query.toString()
  const url = `${API_BASE_URL}/api/travel/packages/${
    queryString ? `?${queryString}` : ''
  }`

  const response = await fetch(url, {
    method: 'GET',
    headers: authHeaders(),
  })

  if (!response.ok) {
    throw new Error(
      await parseError(response, '패키지 목록을 불러오지 못했습니다.'),
    )
  }

  return response.json()
}

export async function getPackageDetail(id) {
  const response = await fetch(
    `${API_BASE_URL}/api/travel/packages/${id}/`,
    {
      method: 'GET',
      headers: authHeaders(),
    },
  )

  if (!response.ok) {
    throw new Error(
      await parseError(response, '패키지 상세 정보를 불러오지 못했습니다.'),
    )
  }

  return response.json()
}