import { createContext, useContext, useEffect, useState } from 'react'
import { API_BASE_URL } from '../api/config.js'

const AuthContext = createContext(null)

const normalizeUser = (user) => ({
  id: user.id,
  email: user.email,
  nickname: user.nickname,
  profileImage: user.profile_image,
  provider: user.provider,
  preferredStyle: user.preferred_style,
  dateJoined: user.date_joined,
})

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const restoreLogin = async () => {
      const accessToken = localStorage.getItem('accessToken')

      if (!accessToken) {
        setLoading(false)
        return
      }

      try {
        const response = await fetch(
          `${API_BASE_URL}/api/accounts/me/`,
          {
            headers: {
              Authorization: `Bearer ${accessToken}`,
            },
          },
        )

        if (!response.ok) {
          throw new Error('저장된 로그인 정보가 유효하지 않습니다.')
        }

        const userData = await response.json()
        setUser(normalizeUser(userData))
      } catch (error) {
        console.error(error)

        localStorage.removeItem('accessToken')
        localStorage.removeItem('refreshToken')
        setUser(null)
      } finally {
        setLoading(false)
      }
    }

    restoreLogin()
  }, [])

  const login = async (provider, token) => {
    setLoading(true)

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/accounts/${provider}/`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(
            provider == 'kakao'
            ? { code: token}
            : { token },
          ),
        },
      )

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || '로그인에 실패했습니다.')
      }

      localStorage.setItem('accessToken', data.access)
      localStorage.setItem('refreshToken', data.refresh)

      const userResponse = await fetch(
        `${API_BASE_URL}/api/accounts/me/`,
        {
          headers: {
            Authorization: `Bearer ${data.access}`,
          },
        },
      )

      const userData = await userResponse.json()

      if (!userResponse.ok) {
        throw new Error(
          userData.detail || '사용자 정보를 불러오지 못했습니다.',
        )
      }

      const normalizedUser = normalizeUser(userData)

      setUser(normalizedUser)

      return normalizedUser
    } finally {
      setLoading(false)
    }
  }

  const logout = async () => {
    const accessToken = localStorage.getItem('accessToken')
    const refreshToken = localStorage.getItem('refreshToken')

    try {
      if (accessToken && refreshToken) {
        await fetch(`${API_BASE_URL}/api/accounts/logout/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify({
            refresh: refreshToken,
          }),
        })
      }
    } finally {
      localStorage.removeItem('accessToken')
      localStorage.removeItem('refreshToken')
      setUser(null)
    }
  }

  const updateProfile = (partial) => {
    setUser((prev) => (
      prev
        ? {
            ...prev,
            ...partial,
          }
        : prev
    ))
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoggedIn: !!user,
        loading,
        login,
        logout,
        updateProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)

  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider')
  }

  return ctx
}
