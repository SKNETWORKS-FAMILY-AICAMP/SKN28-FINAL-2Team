import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { GoogleLogin } from '@react-oauth/google'
import { useAuth } from '../context/AuthContext.jsx'
import styles from './login/login.module.css'

export default function LoginPage() {
  const { login, loading } = useAuth()
  const [pendingProvider, setPendingProvider] = useState(null)
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const handleGoogleSuccess = async (credentialResponse) => {
    try {
      setError('')
      setPendingProvider('google')

      await login('google', credentialResponse.credential)

      const next = searchParams.get('next') || '/'
      navigate(next, { replace: true })
    } catch (err) {
      console.error(err)
      setError(err.message || 'Google 로그인에 실패했습니다.')
    } finally {
      setPendingProvider(null)
    }
  }

  const handleGoogleError = () => {
    setError('Google 로그인에 실패했습니다.')
    setPendingProvider(null)
  }

  const handleKakaoLogin = () => {
    setError('')
    setPendingProvider('kakao')

    try {
      if (!window.Kakao) {
        throw new Error('카카오 로그인 SDK를 불러오지 못했습니다.')
      }

      if (!window.Kakao.isInitialized()) {
        window.Kakao.init(import.meta.env.VITE_KAKAO_JAVASCRIPT_KEY)
      }

      const next = searchParams.get('next') || '/'
      sessionStorage.setItem('kakaoLoginNext', next)

      window.Kakao.Auth.authorize({
        redirectUri:
          import.meta.env.VITE_KAKAO_REDIRECT_URI ||
          `${window.location.origin}/oauth/kakao/callback`,
        prompt: 'login',
      })
    } catch (err) {
      console.error(err)
      setError(err.message || '카카오 로그인에 실패했습니다.')
      setPendingProvider(null)
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.blob1}></div>
      <div className={styles.blob2}></div>

      <div className={styles.card}>
        <div className={styles.logo}>
          <span className={styles.logoMark}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path
                d="M12 2c4 3 6 7 6 11a6 6 0 0 1-12 0c0-4 2-8 6-11z"
                fill="#fff"
              />
            </svg>
          </span>
          탐나플랜
        </div>

        <h1>로그인하고 시작해요</h1>

        <p>
          로그인하면 만든 일정을 저장하고, 패키지를 찜하고,
          <br />
          예약 내역을 확인할 수 있어요.
        </p>

        <div className={styles.btns}>
          <div style={{ position: 'relative' }}>
            <button
              className={`${styles.socialBtn} ${styles.google}`}
              disabled={loading}
              type="button"
            >
              {pendingProvider === 'google' && loading ? (
                <span className={styles.spinner}></span>
              ) : (
                <span className={styles.googleIcon}>G</span>
              )}
              Google로 계속하기
            </button>

            <div
              style={{
                position: 'absolute',
                inset: 0,
                opacity: 0,
                overflow: 'hidden',
              }}
            >
              <GoogleLogin
                onSuccess={handleGoogleSuccess}
                onError={handleGoogleError}
                width="1000"
              />
            </div>
          </div>

          <button
            className={`${styles.socialBtn} ${styles.kakao}`}
            onClick={handleKakaoLogin}
            disabled={loading}
            type="button"
          >
            {pendingProvider === 'kakao' && loading ? (
              <span className={styles.spinner}></span>
            ) : (
              <span className={styles.kakaoIcon}>💬</span>
            )}
            카카오로 계속하기
          </button>
        </div>

        {error && <p>{error}</p>}

        <div className={styles.divider}>또는</div>

        <Link to="/" className={styles.backLink}>
          ← 로그인 없이 둘러보기
        </Link>
      </div>
    </div>
  )
}
