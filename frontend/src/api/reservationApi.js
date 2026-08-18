import api, { extractErrorMessage } from './axios'

export async function getReservations() {
  try {
    const { data } = await api.get('/reservations/')
    return data
  } catch (error) {
    throw new Error(extractErrorMessage(error, '예약 목록을 불러오지 못했습니다.'))
  }
}

export async function getReservation(id) {
  try {
    const { data } = await api.get(`/reservations/${id}/`)
    return data
  } catch (error) {
    throw new Error(extractErrorMessage(error, '예약 상세 정보를 불러오지 못했습니다.'))
  }
}

export async function getReservation(id) {
  const response = await fetch(`${API_BASE_URL}/api/reservations/${id}/`, {
    method: 'GET',
    headers: authHeaders(),
  })

  if (!response.ok) {
    throw new Error(
      await parseError(response, '예약 상세 정보를 불러오지 못했습니다.'),
    )
  }

  return response.json()
}

export async function createReservation(paymentMethod, options = {}) {
  const { packageIds, cartItemIds, itineraryId } = options

  try {
    const { data } = await api.post('/reservations/', {
      payment_method: paymentMethod,
      ...(Array.isArray(packageIds) && packageIds.length > 0
        ? { package_ids: packageIds }
        : {}),
      ...(Array.isArray(cartItemIds) && cartItemIds.length > 0
        ? { cart_item_ids: cartItemIds }
        : {}),
      ...(itineraryId ? { itinerary_id: itineraryId } : {}),
    })
    return data
  } catch (error) {
    throw new Error(extractErrorMessage(error, '예약을 생성하지 못했습니다.'))
  }
}

export async function cancelReservation(id) {
  try {
    const { data } = await api.patch(`/reservations/${id}/cancel/`)
    return data
  } catch (error) {
    throw new Error(extractErrorMessage(error, '예약을 취소하지 못했습니다.'))
  }
}
