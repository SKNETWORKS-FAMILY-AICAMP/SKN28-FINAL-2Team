import { useNavigate } from 'react-router-dom'
import styles from './CartWidget.module.css'
import cx from '../utils/cx.js'
import { useCart } from '../context/CartContext.jsx'
import { won } from '../data/packages.js'

export default function CartWidget() {
  const {
    cartPackages,
    isOpen,
    openCart,
    closeCart,
    updateQuantity,
    removeFromCart,
    clearCart,
    totalCount,
    totalPrice,
  } = useCart()

  const navigate = useNavigate()

  return (
    <>
      {/* 플로팅 장바구니 버튼 */}
      <button className={styles.fab} onClick={openCart} aria-label="장바구니 열기">
        🛒
        {totalCount > 0 && <span className={styles.fabBadge}>{totalCount}</span>}
      </button>

      {isOpen && (
        <div className={styles.overlay} onClick={closeCart}>
          <div className={styles.drawer} onClick={(e) => e.stopPropagation()}>
            <div className={styles.drawerHead}>
              <div>
                <div className={styles.sectionTag}>🛒 패키지 장바구니</div>
                <h3>담아둔 패키지 {cartPackages.length}개</h3>
              </div>
              <button className={styles.closeBtn} onClick={closeCart} aria-label="닫기">
                ✕
              </button>
            </div>

            <div className={styles.drawerBody}>
              {cartPackages.length === 0 ? (
                <div className={styles.empty}>
                  <div className={styles.emptyIcon}>🛒</div>
                  <h4>장바구니가 비어있어요</h4>
                  <p>마음에 드는 패키지를 담아보세요.</p>
                </div>
              ) : (
                cartPackages.map((item) => (
                  <div className={styles.cartItem} key={item.cartId}>
                    <div className={styles.cartItemTop}>
                      <div className={styles.cartThumb}>
                        {item.package.thumbnailUrl || item.package.thumbnail_url ? (
                          <img
                            src={item.package.thumbnailUrl || item.package.thumbnail_url}
                            alt={item.package.name}
                          />
                        ) : (
                          item.package.thumbnail || '🎁'
                        )}
                      </div>
                      <div className={styles.cartInfo}>
                        <h5>{item.package.name}</h5>
                        <div className={styles.price}>{won(item.package.price)}</div>
                      </div>
                      <button
                        className={styles.removeBtn}
                        onClick={() => removeFromCart(item.cartId)}
                        aria-label="삭제"
                        title="삭제"
                      >
                        🗑️
                      </button>
                    </div>

                    <div className={styles.qtyRow}>
                      <span className={styles.qtyLabel}>수량</span>
                      <div className={styles.qtyStepper}>
                        <button
                          onClick={() => updateQuantity(item.cartId, -1)}
                          disabled={item.quantity <= 1}
                          aria-label="수량 감소"
                        >
                          –
                        </button>
                        <span>{item.quantity}</span>
                        <button onClick={() => updateQuantity(item.cartId, 1)} aria-label="수량 증가">
                          +
                        </button>
                      </div>
                      <span className={styles.lineTotal}>{won(item.package.price * item.quantity)}</span>
                    </div>
                  </div>
                ))
              )}
            </div>

            {cartPackages.length > 0 && (
              <div className={styles.drawerFoot}>
                <div className={styles.totalRow}>
                  <span>총 결제 예정 금액</span>
                  <b>{won(totalPrice)}</b>
                </div>
                <div className={styles.footActions}>
                  <button className={cx(styles.btn, styles.ghost)} onClick={clearCart}>
                    전체 삭제
                  </button>
                  <button
                    className={cx(styles.btn, styles.primary)}
                    onClick={() => {
                      closeCart()
                      navigate('/booking', {
                        state : {
                          bookingSource: 'cart',
                        },
                      })
                    }}
                  >
                    예약하기 →
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  )
}
