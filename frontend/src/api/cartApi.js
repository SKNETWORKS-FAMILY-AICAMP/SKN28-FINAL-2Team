import api, { extractErrorMessage } from './axios'

export async function getCart() {
  try {
    const { data } = await api.get('/cart/')
    return data
  } catch (error) {
    throw new Error(extractErrorMessage(error, '장바구니를 불러오지 못했습니다.'))
  }
}

export async function addToCart(packageId, options = {}) {
  try {
    const { data } = await api.post('/cart/', {
      product_type: options.productType || 'stored_package',
      ...(packageId != null && { package_id: packageId }),
      ...(options.itineraryId != null && {
        itinerary_id: options.itineraryId,
      }),
    })
    return data
  } catch (error) {
    throw new Error(extractErrorMessage(error, '장바구니에 추가하지 못했습니다.'))
  }
}

export async function removeFromCart(cartItemId) {
  try {
    await api.delete(`/cart/${cartItemId}/`)
  } catch (error) {
    throw new Error(extractErrorMessage(error, '장바구니에서 삭제하지 못했습니다.'))
  }
}

export async function updateCartItem(cartItemId, updates) {
  try {
    const { data } = await api.patch(`/cart/${cartItemId}/`, updates)
    return data
  } catch (error) {
    throw new Error(extractErrorMessage(error, '장바구니 정보를 수정하지 못했습니다.'))
  }
}

export async function clearCart() {
  try {
    await api.delete('/cart/')
  } catch (error) {
    throw new Error(extractErrorMessage(error, '장바구니를 비우지 못했습니다.'))
  }
}
