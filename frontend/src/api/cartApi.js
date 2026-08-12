import { API_BASE_URL } from './config'

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

    if (data.message) {
      return data.message
    }

    if (data.package_id) {
      return Array.isArray(data.package_id)
        ? data.package_id[0]
        : data.package_id
    }
  } catch {
    // 응답 본문이 없으면 기본 메시지 사용
  }

  return fallbackMessage
}

export async function getCart() {
  const response = await fetch(`${API_BASE_URL}/api/cart/`, {
    method: 'GET',
    headers: authHeaders(),
  })

  if (!response.ok) {
    throw new Error(
      await parseError(response, '장바구니를 불러오지 못했습니다.'),
    )
  }

  return response.json()
}

export async function addToCart(packageId) {
  const response = await fetch(`${API_BASE_URL}/api/cart/`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({
      package_id: packageId,
    }),
  })

  if (!response.ok) {
    throw new Error(
      await parseError(response, '장바구니에 추가하지 못했습니다.'),
    )
  }

  return response.json()
}

export async function removeFromCart(cartItemId) {
  const response = await fetch(
    `${API_BASE_URL}/api/cart/${cartItemId}/`,
    {
      method: 'DELETE',
      headers: authHeaders(),
    },
  )

  if (!response.ok) {
    throw new Error(
      await parseError(response, '장바구니에서 삭제하지 못했습니다.'),
    )
  }
}

export async function updateCartItem(cartItemId, updates) {
  const response = await fetch(
    `${API_BASE_URL}/api/cart/${cartItemId}/`,
    {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify(updates),
    },
  )

  if (!response.ok) {
    throw new Error(
      await parseError(response, '장바구니 정보를 수정하지 못했습니다.'),
    )
  }

  return response.json()
}

export async function clearCart() {
  const response = await fetch(`${API_BASE_URL}/api/cart/`, {
    method: 'DELETE',
    headers: authHeaders(),
  })

  if (!response.ok) {
    throw new Error(
      await parseError(response, '장바구니를 비우지 못했습니다.'),
    )
  }
}
