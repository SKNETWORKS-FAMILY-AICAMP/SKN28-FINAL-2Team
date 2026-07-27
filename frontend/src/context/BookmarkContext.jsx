import { createContext, useContext, useState } from 'react'

const BookmarkContext = createContext(null)

// 백엔드 POST /api/bookmarks/ (담기) · DELETE /api/bookmarks/{id}/ (해제) 와 같은 동작을
// 앱 전역 상태로 흉내낸다. 아직 API 연결 전이라 새로고침하면 초기화된다.
export function BookmarkProvider({ children }) {
  const [bookmarkedIds, setBookmarkedIds] = useState(new Set())

  const toggle = (packageId) => {
    setBookmarkedIds((prev) => {
      const next = new Set(prev)
      if (next.has(packageId)) {
        next.delete(packageId)
      } else {
        next.add(packageId)
      }
      return next
    })
  }

  const isBookmarked = (packageId) => bookmarkedIds.has(packageId)

  return (
    <BookmarkContext.Provider value={{ bookmarkedIds, toggle, isBookmarked }}>
      {children}
    </BookmarkContext.Provider>
  )
}

export function useBookmarks() {
  const ctx = useContext(BookmarkContext)
  if (!ctx) throw new Error('useBookmarks must be used within BookmarkProvider')
  return ctx
}
