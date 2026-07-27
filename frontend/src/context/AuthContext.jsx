import { createContext, useContext, useState } from 'react'

const AuthContext = createContext(null)

// 백엔드 GET/PATCH /api/accounts/me/ 응답 형태와 필드명을 맞춤
const MOCK_USERS = {
  google: {
    id: 1,
    email: 'jeju.lover@gmail.com',
    nickname: '제주러버',
    profileImage: '',
    provider: 'google',
    phone: '',
    preferredStyle: '',
    preferredBudget: null,
    dateJoined: '2026-03-14',
  },
  kakao: {
    id: 2,
    email: 'jeju.lover@kakao.com',
    nickname: '제주러버',
    profileImage: '',
    provider: 'kakao',
    phone: '',
    preferredStyle: '',
    preferredBudget: null,
    dateJoined: '2026-03-14',
  },
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(false)

  // 실제로는 구글/카카오 SDK 토큰을 POST /api/accounts/google|kakao/ 로 보내고
  // 응답으로 온 JWT를 저장하지만, 아직 연결 전이라 짧은 로딩 후 목업 유저로 로그인 처리한다.
  const login = (provider) =>
    new Promise((resolve) => {
      setLoading(true)
      setTimeout(() => {
        setUser(MOCK_USERS[provider])
        setLoading(false)
        resolve(MOCK_USERS[provider])
      }, 700)
    })

  const logout = () => setUser(null)

  const updateProfile = (partial) => setUser((prev) => (prev ? { ...prev, ...partial } : prev))

  return (
    <AuthContext.Provider
      value={{ user, isLoggedIn: !!user, loading, login, logout, updateProfile }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
