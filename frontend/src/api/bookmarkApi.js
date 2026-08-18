import api, { extractErrorMessage } from './axios'

export async function getBookmarks() {
  try {
    const { data } = await api.get('/bookmarks/')
    return data
  } catch (error) {
    throw new Error(extractErrorMessage(error, '북마크 목록을 불러오지 못했습니다.'))
  }
}

export async function createBookmark(packageId) {
  try {
    const { data } = await api.post('/bookmarks/', { package_id: packageId })
    return data
  } catch (error) {
    throw new Error(extractErrorMessage(error, '북마크를 추가하지 못했습니다.'))
  }
}

export async function deleteBookmark(bookmarkId) {
  try {
    await api.delete(`/bookmarks/${bookmarkId}/`)
  } catch (error) {
    throw new Error(extractErrorMessage(error, '북마크를 삭제하지 못했습니다.'))
  }
}
