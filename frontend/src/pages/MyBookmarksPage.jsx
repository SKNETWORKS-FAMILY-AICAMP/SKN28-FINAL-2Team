import { Link } from 'react-router-dom'
import styles from './account/account.module.css'
import cx from '../utils/cx.js'
import AccountHeader from './account/AccountHeader.jsx'
import AccountTabs from './account/AccountTabs.jsx'
import { useBookmarks } from '../context/BookmarkContext.jsx'
import { won } from '../data/packages.js'

export default function MyBookmarksPage() {
  const { bookmarks, toggle } = useBookmarks()

  return (
    <div className={styles.page}>
      <AccountHeader />
      <div className={styles.wrap}>
        <AccountTabs active="/my/bookmarks" />

        <div className={styles.pageHead}>
          <div className={styles.sectionTag}>✓ 찜한 패키지</div>
          <h1>찜한 패키지</h1>
          <p>마음에 드는 패키지를 하트로 찜해두면 여기서 모아볼 수 있어요.</p>
        </div>

        <div className={styles.card}>
          {bookmarks.length === 0 ? (
            <div className={styles.empty}>
              <div className={styles.icon}>🤍</div>
              <h4>아직 찜한 패키지가 없어요</h4>
              <p>랜딩 페이지나 예약 화면에서 하트를 눌러 패키지를 찜해보세요.</p>
              <Link to="/#packages" className={cx(styles.btn, styles.primary)}>
                패키지 둘러보기 →
              </Link>
            </div>
          ) : (
            bookmarks.map((bookmark) => {
              const p = bookmark.package_detail

              if (!p) return null

              return (
                <div className={styles.listItem} key={bookmark.id}>
                  <div className={styles.listThumb}>🎁</div>

                  <div className={styles.listInfo}>
                    <h5>{p.name}</h5>
                    <p>{p.description}</p>

                    <span
                      className={styles.badge}
                      style={{
                        background: 'var(--bg-soft)',
                        color: 'var(--muted)',
                      }}
                    >
                      {p.region} · {p.duration_days}일
                    </span>
                  </div>

                  <div className={styles.listMeta}>
                    <div className={styles.price}>{won(p.price)}</div>

                    <button
                      className={cx(styles.btn, styles.ghost, styles.sm)}
                      style={{ marginTop: 8 }}
                      onClick={() => toggle(p.id)}
                    >
                      찜 해제
                    </button>
                  </div>
                </div>
              )
            })
          )}
        </div>
      </div>
    </div>
  )
}