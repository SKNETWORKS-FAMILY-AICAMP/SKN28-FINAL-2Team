import { useState } from 'react'
import styles from './account/account.module.css'
import cx from '../utils/cx.js'
import AccountHeader from './account/AccountHeader.jsx'
import AccountTabs from './account/AccountTabs.jsx'
import { useAuth } from '../context/AuthContext.jsx'

const STYLE_OPTIONS = [
  { value: '', label: '선택 안 함' },
  { value: 'family', label: '가족형' },
  { value: 'healing', label: '힐링형' },
  { value: 'activity', label: '액티비티형' },
  { value: 'food', label: '맛집형' },
]

const PROVIDER_LABEL = { google: 'Google 계정', kakao: 'Kakao 계정' }

export default function MyPage() {
  const { user, updateProfile } = useAuth()
  const [form, setForm] = useState({
    nickname: user.nickname,
    phone: user.phone || '',
    preferredStyle: user.preferredStyle || '',
    preferredBudget: user.preferredBudget || '',
  })
  const [saved, setSaved] = useState(false)
  const [saving, setSaving] = useState(false)

  const handleChange = (key) => (e) => {
    setForm((prev) => ({ ...prev, [key]: e.target.value }))
    setSaved(false)
  }

  const handleSave = () => {
    setSaving(true)
    // 실제로는 PATCH /api/accounts/me/ 호출 — 아직 연결 전이라 컨텍스트만 갱신
    setTimeout(() => {
      updateProfile({
        nickname: form.nickname,
        phone: form.phone,
        preferredStyle: form.preferredStyle,
        preferredBudget: form.preferredBudget ? Number(form.preferredBudget) : null,
      })
      setSaving(false)
      setSaved(true)
    }, 500)
  }

  return (
    <div className={styles.page}>
      <AccountHeader />
      <div className={styles.wrap}>
        <AccountTabs active="/mypage" />

        <div className={styles.pageHead}>
          <div className={styles.sectionTag}>✓ 마이페이지</div>
          <h1>내 정보 관리</h1>
          <p>기본 정보와 여행 선호 정보를 관리해요. 다음 일정 추천에 활용돼요.</p>
        </div>

        <div className={styles.card}>
          <div className={styles.avatarRow}>
            <div className={styles.avatarBig}>🙂</div>
            <div>
              <h3>{user.nickname}</h3>
              <p>{user.email}</p>
              <span className={styles.providerBadge}>{PROVIDER_LABEL[user.provider]}로 로그인됨</span>
            </div>
          </div>

          <div className={styles.field}>
            <label>닉네임</label>
            <input type="text" value={form.nickname} onChange={handleChange('nickname')} />
          </div>

          <div className={styles.field}>
            <label>이메일</label>
            <input type="email" value={user.email} disabled />
          </div>

          <div className={styles.field}>
            <label>연락처</label>
            <input
              type="tel"
              placeholder="010-0000-0000"
              value={form.phone}
              onChange={handleChange('phone')}
            />
          </div>

          <div className={styles.fieldRow}>
            <div className={styles.field}>
              <label>선호 여행 스타일</label>
              <select value={form.preferredStyle} onChange={handleChange('preferredStyle')}>
                {STYLE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <div className={styles.field}>
              <label>선호 예산 (1인당)</label>
              <input
                type="number"
                placeholder="500000"
                value={form.preferredBudget}
                onChange={handleChange('preferredBudget')}
              />
            </div>
          </div>

          <div className={styles.saveBar}>
            <button className={cx(styles.btn, styles.primary)} onClick={handleSave} disabled={saving}>
              {saving ? '저장 중…' : '변경사항 저장'}
            </button>
            {saved && <span className={styles.savedMsg}>✓ 저장됐어요</span>}
          </div>
        </div>
      </div>
    </div>
  )
}
