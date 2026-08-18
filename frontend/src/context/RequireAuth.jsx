import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './AuthContext.jsx'

export default function RequireAuth({ children }) {
  const { isLoggedIn } = useAuth()
  const location = useLocation()

  if (!isLoggedIn) {
    return <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />
  }

  return children
}
