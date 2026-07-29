import { createContext, useContext, useEffect, useState } from 'react'

import { createBookmark, deleteBookmark, getBookmarks } from '../api/bookmarkApi'
import { useAuth } from './AuthContext'

const BookmarkContext = createContext(null)

export function BookmarkProvider({ children }) {
  const { isLoggedIn, loading: authLoading } = useAuth()

  const [bookmarkedIds, setBookmarkedIds] = useState(new Set())
  const [bookmarkIdByPackageId, setBookmarkIdByPackageId] = useState({})

  useEffect(() => {
    const loadBookmarks = async () => {
      if (authLoading) return

      if (!isLoggedIn) {
        setBookmarkedIds(new Set())
        setBookmarkIdByPackageId({})
        return
      }

      try {
        const bookmarks = await getBookmarks()
        const nextIds = new Set()
        const nextBookmarkMap = {}

        bookmarks.forEach((bookmark) => {
          const packageId =
            typeof bookmark.package === 'object'
              ? bookmark.package.id
              : bookmark.package

          nextIds.add(packageId)
          nextBookmarkMap[packageId] = bookmark.id
        })

        setBookmarkedIds(nextIds)
        setBookmarkIdByPackageId(nextBookmarkMap)
      } catch (error) {
        console.error('북마크 목록 조회 실패:', error)
      }
    }

    loadBookmarks()
  }, [isLoggedIn, authLoading])

  const toggle = async (packageId) => {
    if (!isLoggedIn) {
      alert('로그인 후 이용할 수 있습니다.')
      return
    }

    try {
      if (bookmarkedIds.has(packageId)) {
        const bookmarkId = bookmarkIdByPackageId[packageId]

        if (!bookmarkId) return

        await deleteBookmark(bookmarkId)

        setBookmarkedIds((prev) => {
          const next = new Set(prev)
          next.delete(packageId)
          return next
        })

        setBookmarkIdByPackageId((prev) => {
          const next = { ...prev }
          delete next[packageId]
          return next
        })
      } else {
        const bookmark = await createBookmark(packageId)

        setBookmarkedIds((prev) => {
          const next = new Set(prev)
          next.add(packageId)
          return next
        })

        setBookmarkIdByPackageId((prev) => ({
          ...prev,
          [packageId]: bookmark.id,
        }))
      }
    } catch (error) {
      console.error('북마크 변경 실패:', error)
      alert(error.message)
    }
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