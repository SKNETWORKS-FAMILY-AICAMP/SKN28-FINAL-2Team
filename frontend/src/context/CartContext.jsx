import { createContext, useContext, useEffect, useState } from 'react'
import { useAuth } from './AuthContext.jsx'
import {
  getCart,
  addToCart as addToCartApi,
  updateCartItem,
  removeFromCart as removeFromCartApi,
  clearCart as clearCartApi,
} from '../api/cartApi.js'

const CartContext = createContext(null)

const normalizeCartItem = (item) => ({
  cartId: item.id,
  packageId: item.package,
  quantity: item.quantity,
  optionDate: item.option_date || '',
  optionPeople: item.option_people ?? 2,
  package: item.package_detail,
})

export function CartProvider({ children }) {
  const { user, loading } = useAuth()

  const [items, setItems] = useState([])
  const [isOpen, setIsOpen] = useState(false)

  const openCart = () => setIsOpen(true)
  const closeCart = () => setIsOpen(false)
  const toggleCart = () => setIsOpen((v) => !v)

  const loadCart = async () => {
    try {
      const data = await getCart()

      const cartItems = Array.isArray(data)
        ? data
        : data.items || data.cart_items || data.results || []

      setItems(cartItems.map(normalizeCartItem))
    } catch (error) {
      console.error('장바구니 조회 실패:', error)
      setItems([])
    }
  }

  useEffect(() => {
    if (loading) return

    if (!user) {
      setItems([])
      return
    }

    loadCart()
  }, [loading, user])

  const addToCart = async (packageId, options = {}) => {
    try {
      let createdItem = await addToCartApi(packageId)

      if (options.optionDate || options.optionPeople) {
        createdItem = await updateCartItem(createdItem.id, {
          ...(options.optionDate && {
            option_date: options.optionDate,
          }),
          ...(options.optionPeople && {
            option_people: options.optionPeople,
          }),
        })
      }

      const normalizedItem = normalizeCartItem(createdItem)

      setItems((prev) => {
        const exists = prev.some(
          (item) => item.cartId === normalizedItem.cartId,
        )

        if (exists) {
          return prev.map((item) =>
            item.cartId === normalizedItem.cartId
              ? normalizedItem
              : item,
          )
        }

        return [...prev, normalizedItem]
      })

      return normalizedItem
    } catch (error) {
      console.error('장바구니 추가 실패:', error)
      throw error
    }
  }

  const updateQuantity = async (cartId, delta) => {
    const currentItem = items.find((item) => item.cartId === cartId)

    if (!currentItem) return

    const quantity = Math.min(
      9,
      Math.max(1, currentItem.quantity + delta),
    )

    try {
      const updatedItem = await updateCartItem(cartId, {
        quantity,
      })

      const normalizedItem = normalizeCartItem(updatedItem)

      setItems((prev) =>
        prev.map((item) =>
          item.cartId === cartId ? normalizedItem : item,
        ),
      )
    } catch (error) {
      console.error('장바구니 수량 수정 실패:', error)
      throw error
    }
  }

  const updateOptions = async (cartId, patch) => {
    const requestData = {}

    if (patch.optionDate !== undefined) {
      requestData.option_date = patch.optionDate
    }

    if (patch.optionPeople !== undefined) {
      requestData.option_people = patch.optionPeople
    }

    try {
      const updatedItem = await updateCartItem(
        cartId,
        requestData,
      )

      const normalizedItem = normalizeCartItem(updatedItem)

      setItems((prev) =>
        prev.map((item) =>
          item.cartId === cartId ? normalizedItem : item,
        ),
      )
    } catch (error) {
      console.error('장바구니 옵션 수정 실패:', error)
      throw error
    }
  }

  const removeFromCart = async (cartId) => {
    try {
      await removeFromCartApi(cartId)

      setItems((prev) =>
        prev.filter((item) => item.cartId !== cartId),
      )
    } catch (error) {
      console.error('장바구니 삭제 실패:', error)
      throw error
    }
  }

  const clearCart = async () => {
    try {
      await clearCartApi()
      setItems([])
    } catch (error) {
      console.error('장바구니 전체 삭제 실패:', error)
      throw error
    }
  }

  const cartPackages = items.filter((item) => item.package)

  const totalCount = items.reduce(
    (sum, item) => sum + item.quantity,
    0,
  )

  const totalPrice = cartPackages.reduce(
    (sum, item) =>
      sum + Number(item.package.price) * item.quantity,
    0,
  )

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
        refreshCart: loadCart,
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

  if (!ctx) {
    throw new Error(
      'useCart must be used within CartProvider',
    )
  }

  return ctx
}