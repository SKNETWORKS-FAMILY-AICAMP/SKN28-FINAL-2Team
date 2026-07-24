import { Link } from 'react-router-dom'
import styles from './chat.module.css'
import cx from '../../utils/cx.js'

const CONDITIONS = [
  { ic: '👥', label: '여행 인원', value: '부모님 (2명)' },
  { ic: '📅', label: '여행 기간', value: '2박 3일' },
  { ic: '🍃', label: '여행 스타일', value: '힐링 / 여유로운 여행' },
  { ic: '💰', label: '예산', value: '1인당 50만원' },
]

export default function SummaryColumn({ ready }) {
  return (
    <div className={styles.summaryCol}>
      <div className={cx(styles.blob, styles.blob1)}></div>
      <div className={cx(styles.blob, styles.blob2)}></div>

      <div className={styles.heroPanel}>
        <div className={styles.eyebrow}>
          <span className={styles.dot}></span>
          {ready ? '일정 준비 완료!' : 'AI가 조건을 정리하는 중'}
        </div>

        <div className={styles.mascotWrap}>
          <svg className={styles.mascot} viewBox="0 0 200 220" fill="none">
            <ellipse cx="100" cy="205" rx="50" ry="9" fill="#1B211D" opacity="0.08" />
            <g className={styles.dolharubang}>
              <path
                d="M55 120c0-45 20-80 45-80s45 35 45 80c0 15-8 25-45 25s-45-10-45-25z"
                fill="#F5E6C8"
                stroke="#1B211D"
                strokeWidth="3"
              />
              <circle cx="80" cy="105" r="5" fill="#1B211D" />
              <circle cx="120" cy="105" r="5" fill="#1B211D" />
              <path d="M85 122c5 5 25 5 30 0" stroke="#1B211D" strokeWidth="3" strokeLinecap="round" />
              <path
                d="M63 92c5-14 15-22 37-22s32 8 37 22"
                stroke="#1B211D"
                strokeWidth="3"
                fill="none"
                strokeLinecap="round"
              />
              <rect x="70" y="140" width="60" height="55" rx="18" fill="#2E9E62" stroke="#1B211D" strokeWidth="3" />
              <circle cx="100" cy="160" r="7" fill="#C7E263" stroke="#1B211D" strokeWidth="2.5" />
              <g className={styles.hand}>
                <path d="M130 150c15-5 25 2 28 14" stroke="#1B211D" strokeWidth="6" strokeLinecap="round" />
                <circle cx="160" cy="158" r="9" fill="#F5E6C8" stroke="#1B211D" strokeWidth="3" />
              </g>
            </g>
          </svg>
        </div>

        {ready ? (
          <h1>
            여행 일정이
            <br />
            <span className={styles.accent}>준비됐어요</span>
          </h1>
        ) : (
          <h1>
            AI가 당신만을 위한
            <br />
            <span className={styles.accent}>여행을 준비</span>하고 있어요
          </h1>
        )}
        <p>
          {ready
            ? '대화로 입력한 조건을 바탕으로 동선까지 짜인 맞춤 일정이 완성됐어요.'
            : '대화를 통해 입력한 조건을 바탕으로 동선까지 짜인 맞춤 일정을 만들고 있어요.'}
        </p>

        <div className={styles.progressTrack}>
          <div className={cx(styles.progressFill, ready && styles.progressFillDone)}></div>
        </div>

        {ready && (
          <Link to="/itinerary" className={cx(styles.btn, styles.primary)} style={{ marginTop: 22, position: 'relative', zIndex: 2 }}>
            완성된 일정 보러가기 →
          </Link>
        )}
      </div>

      <div className={styles.summaryCard}>
        <h4>📋 입력된 조건 요약</h4>
        {CONDITIONS.map((c) => (
          <div className={styles.condRow} key={c.label}>
            <div className={styles.condIc}>{c.ic}</div>
            <div className={styles.condBody}>
              <div className={styles.lbl}>{c.label}</div>
              <div className={styles.val}>{c.value}</div>
            </div>
          </div>
        ))}
      </div>

      <div className={styles.tipNote}>
        <div className={styles.ic}>💡</div>
        <p>
          <b>{ready ? '완성됐어요!' : '조금만 기다려주세요!'}</b> 대화창에서 언제든 조건을 추가하거나
          바꿀 수 있어요. {ready ? '위 버튼으로 확인해보세요.' : '곧 멋진 일정이 완성됩니다.'}
        </p>
      </div>
    </div>
  )
}
