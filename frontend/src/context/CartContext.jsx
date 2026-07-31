import { createContext, useContext, useState } from 'react'
import { PACKAGES } from '../data/packages.js'

const CartContext = createContext(null)

// UI 데모용 목업 장바구니 초기값 (패키지 데이터와 연결)
const INITIAL_CART = [
  { cartId: 'c1', packageId: 1, quantity: 1, optionDate: '2024-08-15', optionPeople: 2 },
  { cartId: 'c2', packageId: 2, quantity: 1, optionDate: '2024-08-15', optionPeople: 2 },
]

let cartIdSeq = INITIAL_CART.length + 1

export function CartProvider({ children }) {
  const [items, setItems] = useState(INITIAL_CART)
  const [isOpen, setIsOpen] = useState(false)

  const openCart = () => setIsOpen(true)
  const closeCart = () => setIsOpen(false)
  const toggleCart = () => setIsOpen((v) => !v)

  const addToCart = (packageId, options = {}) => {
    setItems((prev) => [
      ...prev,
      {
        cartId: `c${cartIdSeq++}`,
        packageId,
        quantity: 1,
        optionDate: options.optionDate || '',
        optionPeople: options.optionPeople || 2,
      },
    ])
  }

  const updateQuantity = (cartId, delta) => {
    setItems((prev) =>
      prev.map((it) =>
        it.cartId === cartId ? { ...it, quantity: Math.min(9, Math.max(1, it.quantity + delta)) } : it
      )
    )
  }

  const updateOptions = (cartId, patch) => {
    setItems((prev) => prev.map((it) => (it.cartId === cartId ? { ...it, ...patch } : it)))
  }

  const removeFromCart = (cartId) => {
    setItems((prev) => prev.filter((it) => it.cartId !== cartId))
  }

  const clearCart = () => setItems([])

  const cartPackages = items
    .map((it) => {
      const pkg = PACKAGES.find((p) => p.id === it.packageId)
      return pkg ? { ...it, package: pkg } : null
    })
    .filter(Boolean)

  const totalCount = items.reduce((sum, it) => sum + it.quantity, 0)
  const totalPrice = cartPackages.reduce((sum, it) => sum + it.package.price * it.quantity, 0)

  return (
    <CartContext.Provider
      value={{
        items,
        cartPackages,
        isOpen,
        openCart,
        closeCart,
        toggleCart,
        addToCart,
        updateQuantity,
        updateOptions,
        removeFromCart,
        clearCart,
        totalCount,
        totalPrice,
      }}
    >
      {children}
    </CartContext.Provider>
  )
}

export function useCart() {
  const ctx = useContext(CartContext)
  if (!ctx) throw new Error('useCart must be used within CartProvider')
  return ctx
}
