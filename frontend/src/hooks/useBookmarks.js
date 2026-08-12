import { useState } from 'react'

// 백엔드 POST /api/bookmarks/ (담기) · DELETE /api/bookmarks/{id}/ (해제) 와 같은 동작을
// 로컬 상태로 흉내낸다. 아직 API 연결 전이라 새로고침하면 초기화된다.
export default function useBookmarks(initialIds = []) {
  const [bookmarked, setBookmarked] = useState(new Set(initialIds))

  const toggle = (packageId) => {
    setBookmarked((prev) => {
      const next = new Set(prev)
      if (next.has(packageId)) {
        next.delete(packageId)
      } else {
        next.add(packageId)
      }
      return next
    })
  }

  const isBookmarked = (packageId) => bookmarked.has(packageId)

  return { isBookmarked, toggle }
}
