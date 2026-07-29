const API_BASE_URL = 'http://localhost:8000'

const getAccessToken = () => localStorage.getItem('accessToken')

const authHeaders = () => {
  const accessToken = getAccessToken()

  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${accessToken}`,
  }
}

const parseError = async (response, fallbackMessage) => {
  try {
    const data = await response.json()

    if (data.detail) {
      return data.detail
    }

    if (data.package_id) {
      return Array.isArray(data.package_id)
        ? data.package_id[0]
        : data.package_id
    }
  } catch {
    // 응답 본문이 없는 경우 기본 메시지를 사용한다.
  }

  return fallbackMessage
}

export async function getBookmarks() {
  const response = await fetch(`${API_BASE_URL}/api/bookmarks/`, {
    method: 'GET',
    headers: authHeaders(),
  })

  if (!response.ok) {
    throw new Error(
      await parseError(response, '북마크 목록을 불러오지 못했습니다.'),
    )
  }

  return response.json()
}

export async function createBookmark(packageId) {
  const response = await fetch(`${API_BASE_URL}/api/bookmarks/`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({
      package_id: packageId,
    }),
  })

  if (!response.ok) {
    throw new Error(
      await parseError(response, '북마크를 추가하지 못했습니다.'),
    )
  }

  return response.json()
}

export async function deleteBookmark(bookmarkId) {
  const response = await fetch(
    `${API_BASE_URL}/api/bookmarks/${bookmarkId}/`,
    {
      method: 'DELETE',
      headers: authHeaders(),
    },
  )

  if (!response.ok) {
    throw new Error(
      await parseError(response, '북마크를 삭제하지 못했습니다.'),
    )
  }
}