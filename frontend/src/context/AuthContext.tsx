import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'
import * as api from '../services/api'
import type { AuthUser } from '../services/api'

interface AuthContextValue {
  /** The logged-in user, or null. Check `initializing` before trusting null. */
  user: AuthUser | null
  /** True while the stored token from a previous visit is being validated. */
  initializing: boolean
  login: (email: string, password: string) => Promise<void>
  signup: (email: string, password: string, fullName?: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [initializing, setInitializing] = useState(true)

  // On mount, a token from a previous visit may still be in localStorage.
  // Validate it against /auth/me instead of trusting it: it could be
  // expired or belong to a since-deactivated account.
  useEffect(() => {
    if (!api.getToken()) {
      setInitializing(false)
      return
    }
    api
      .fetchMe()
      .then(setUser)
      .catch(() => api.clearToken())
      .finally(() => setInitializing(false))
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const token = await api.login(email, password)
    api.setToken(token)
    setUser(await api.fetchMe())
  }, [])

  const signup = useCallback(
    async (email: string, password: string, fullName?: string) => {
      await api.signup(email, password, fullName)
      // The signup response has no token by design — log in right after.
      const token = await api.login(email, password)
      api.setToken(token)
      setUser(await api.fetchMe())
    },
    [],
  )

  const logout = useCallback(() => {
    api.clearToken()
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, initializing, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
