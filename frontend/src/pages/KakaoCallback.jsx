import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'

export default function KakaoCallback() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const isProcessing = useRef(false)

  useEffect(() => {
    const handleKakaoCallback = async () => {
      if (isProcessing.current) {
        return
      }

      isProcessing.current = true

      const searchParams = new URLSearchParams(window.location.search)
      const code = searchParams.get('code')

      if (!code) {
        navigate('/login', { replace: true })
        return
      }

      try {
        await login('kakao', code)

        const next =
          sessionStorage.getItem('kakaoLoginNext') || '/mypage'

        sessionStorage.removeItem('kakaoLoginNext')
        navigate(next, { replace: true })
      } catch (err) {
        console.error(err)
        navigate('/login', { replace: true })
      }
    }

    handleKakaoCallback()
  }, [login, navigate])

  return <div>카카오 로그인 처리 중...</div>
}