import api, { extractErrorMessage } from './axios'

export async function getPackages(params = {}) {
  try {
    const { data } = await api.get('/travel/packages/', {
      params: {
        ...(params.category && { category: params.category }),
        ...(params.style && { style: params.style }),
        ...(params.durationDays && { duration_days: params.durationDays }),
        ...(params.maxPrice && { max_price: params.maxPrice }),
      },
    })
    return data
  } catch (error) {
    throw new Error(extractErrorMessage(error, '패키지 목록을 불러오지 못했습니다.'))
  }
}

export async function getPackageDetail(id) {
  try {
    const { data } = await api.get(`/travel/packages/${id}/`)
    return data
  } catch (error) {
    throw new Error(extractErrorMessage(error, '패키지 상세 정보를 불러오지 못했습니다.'))
  }
}
