import { createContext, useContext, useEffect, useState } from 'react'

import {
  createBookmark,
  deleteBookmark,
  getBookmarks,
} from '../api/bookmarkApi'
import { useAuth } from './AuthContext'

const BookmarkContext = createContext(null)

export function BookmarkProvider({ children }) {
  const { isLoggedIn, loading: authLoading } = useAuth()

  const [bookmarks, setBookmarks] = useState([])
  const [bookmarkedIds, setBookmarkedIds] = useState(new Set())
  const [bookmarkIdByPackageId, setBookmarkIdByPackageId] = useState({})

  useEffect(() => {
    const loadBookmarks = async () => {
      if (authLoading) return

      if (!isLoggedIn) {
        setBookmarks([])
        setBookmarkedIds(new Set())
        setBookmarkIdByPackageId({})
        return
      }

      try {
        const data = await getBookmarks()

        const bookmarkList = Array.isArray(data)
          ? data
          : data.results ?? []

        const nextIds = new Set()
        const nextBookmarkMap = {}

        bookmarkList.forEach((bookmark) => {
          const packageId = bookmark.package_db_id

          nextIds.add(packageId)
          nextBookmarkMap[packageId] = bookmark.id
        })

        setBookmarks(bookmarkList)
        setBookmarkedIds(nextIds)
        setBookmarkIdByPackageId(nextBookmarkMap)
      } catch (error) {
        console.error('북마크 목록 조회 실패:', error)
        setBookmarks([])
        setBookmarkedIds(new Set())
        setBookmarkIdByPackageId({})
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

        setBookmarks((prev) =>
          prev.filter((bookmark) => bookmark.id !== bookmarkId),
        )

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

        setBookmarks((prev) => [bookmark, ...prev])

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
    <BookmarkContext.Provider
      value={{
        bookmarks,
        bookmarkedIds,
        toggle,
        isBookmarked,
      }}
    >
      {children}
    </BookmarkContext.Provider>
  )
}

export function useBookmarks() {
  const ctx = useContext(BookmarkContext)

  if (!ctx) {
    throw new Error('useBookmarks must be used within BookmarkProvider')
  }

  return ctx
}
