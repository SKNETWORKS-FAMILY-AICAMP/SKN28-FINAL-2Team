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
  } catch {
    // 응답 본문이 없는 경우 기본 메시지를 사용한다.
  }

  return fallbackMessage
}

export async function getReservations() {
  const response = await fetch(`${API_BASE_URL}/api/reservations/`, {
    method: 'GET',
    headers: authHeaders(),
  })

  if (!response.ok) {
    throw new Error(
      await parseError(response, '예약 목록을 불러오지 못했습니다.'),
    )
  }

  return response.json()
}

export async function createReservation(paymentMethod, options = {}) {
  const { packageIds, cartItemIds, itineraryId } = options

  const response = await fetch(`${API_BASE_URL}/api/reservations/`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({
      payment_method: paymentMethod,
      ...(Array.isArray(packageIds) && packageIds.length > 0
        ? { package_ids: packageIds }
        : {}),
      ...(Array.isArray(cartItemIds) && cartItemIds.length > 0
        ? { cart_item_ids: cartItemIds }
        : {}),
      ...(itineraryId ? { itinerary_id: itineraryId } : {}),
    }),
  })

  if (!response.ok) {
    throw new Error(
      await parseError(response, '예약을 생성하지 못했습니다.'),
    )
  }

  return response.json()
}

export async function cancelReservation(id) {
  const response = await fetch(
    `${API_BASE_URL}/api/reservations/${id}/cancel/`,
    {
      method: 'PATCH',
      headers: authHeaders(),
    },
  )

  if (!response.ok) {
    throw new Error(
      await parseError(response, '예약을 취소하지 못했습니다.'),
    )
  }

  return response.json()
}
