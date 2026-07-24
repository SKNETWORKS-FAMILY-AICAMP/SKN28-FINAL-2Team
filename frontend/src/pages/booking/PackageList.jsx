import styles from './booking.module.css'
import cx from '../../utils/cx.js'

export const PACKAGES = [
  { id: 'stay', icon: '🏨', title: '오션뷰 힐링 숙소', desc: '협재 오션스테이 · 2박', rating: '★ 4.6 (321)', price: 159000 },
  { id: 'car', icon: '🚗', title: '렌터카 3일', desc: '아반떼 CN7 (자차 포함)', rating: '★ 4.7 (532)', price: 89700 },
  { id: 'activity', icon: '🐴', title: '제주 승마 체험 2인', desc: '숲속 승마 트래킹', rating: '★ 4.8 (218)', price: 70000 },
]

export default function PackageList({ selected, onToggle }) {
  return (
    <div className={styles.card}>
      <h4>선택한 패키지</h4>
      {PACKAGES.map((p) => {
        const checked = selected.includes(p.id)
        return (
          <div
            key={p.id}
            className={cx(styles.pkgRow, checked && styles.pkgRowChecked)}
            onClick={() => onToggle(p.id)}
          >
            <div className={cx(styles.checkbox, checked && styles.checkboxChecked)}>{checked ? '✓' : ''}</div>
            <div className={styles.pkgThumb}>{p.icon}</div>
            <div className={styles.pkgInfo}>
              <h5>{p.title}</h5>
              <div className={styles.desc}>{p.desc}</div>
              <div className={styles.rating}>{p.rating}</div>
            </div>
            <div className={styles.pkgPrice}>{p.price.toLocaleString('ko-KR')}원</div>
          </div>
        )
      })}
    </div>
  )
}
