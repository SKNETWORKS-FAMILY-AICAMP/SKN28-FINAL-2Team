import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import styles from './login/login.module.css'

export default function LoginPage() {
  const { login, loading } = useAuth()
  const [pendingProvider, setPendingProvider] = useState(null)
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const handleLogin = async (provider) => {
    setPendingProvider(provider)
    await login(provider)
    const next = searchParams.get('next') || '/mypage'
    navigate(next, { replace: true })
  }

  return (
    <div className={styles.page}>
      <div className={styles.blob1}></div>
      <div className={styles.blob2}></div>

      <div className={styles.card}>
        <div className={styles.logo}>
          <span className={styles.logoMark}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M12 2c4 3 6 7 6 11a6 6 0 0 1-12 0c0-4 2-8 6-11z" fill="#fff" />
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
          <button
            className={`${styles.socialBtn} ${styles.google}`}
            onClick={() => handleLogin('google')}
            disabled={loading}
          >
            {pendingProvider === 'google' && loading ? (
              <span className={styles.spinner}></span>
            ) : (
              <span className={styles.googleIcon}>G</span>
            )}
            Google로 계속하기
          </button>
          <button
            className={`${styles.socialBtn} ${styles.kakao}`}
            onClick={() => handleLogin('kakao')}
            disabled={loading}
          >
            {pendingProvider === 'kakao' && loading ? (
              <span className={styles.spinner}></span>
            ) : (
              <span className={styles.kakaoIcon}>💬</span>
            )}
            카카오로 계속하기
          </button>
        </div>

        <div className={styles.divider}>또는</div>
        <Link to="/" className={styles.backLink}>
          ← 로그인 없이 둘러보기
        </Link>
      </div>
    </div>
  )
}
