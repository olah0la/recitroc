import { useState, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

type Mode = 'login' | 'signup'

function LoginPage() {
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [username, setUsername] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const { login, signup } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      if (mode === 'login') {
        await login(email, password)
      } else {
        await signup(email, password, {
          username: username || undefined,
          firstName: firstName || undefined,
          lastName: lastName || undefined,
        })
      }
      navigate('/swipe')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setSubmitting(false)
    }
  }

  const switchMode = (next: Mode) => {
    setMode(next)
    setError(null)
  }

  return (
    <div className="page">
      <h1>{mode === 'login' ? 'Login' : 'Create account'}</h1>
      <form onSubmit={handleSubmit} className="login-form">
        {mode === 'signup' && (
          <>
            <div className="form-group">
              <label htmlFor="firstName">First name:</label>
              <input
                type="text"
                id="firstName"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                maxLength={255}
              />
            </div>
            <div className="form-group">
              <label htmlFor="lastName">Last name:</label>
              <input
                type="text"
                id="lastName"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                maxLength={255}
              />
            </div>
            <div className="form-group">
              <label htmlFor="username">Username (optional):</label>
              <input
                type="text"
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                minLength={3}
                maxLength={50}
                pattern="[A-Za-z0-9_.\-]+"
                title="Letters, numbers, dots, dashes and underscores"
              />
            </div>
          </>
        )}
        <div className="form-group">
          <label htmlFor="email">Email:</label>
          <input
            type="email"
            id="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <div className="form-group">
          <label htmlFor="password">Password:</label>
          <input
            type="password"
            id="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            // Mirror the backend rules (schemas/user.py) so most mistakes
            // are caught before a round-trip; the server remains the
            // authority.
            minLength={8}
            maxLength={72}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
          />
        </div>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" disabled={submitting}>
          {submitting
            ? 'Please wait…'
            : mode === 'login'
              ? 'Login'
              : 'Sign up'}
        </button>
      </form>
      <p className="form-switch">
        {mode === 'login' ? (
          <>
            No account yet?{' '}
            <button type="button" onClick={() => switchMode('signup')}>
              Create one
            </button>
          </>
        ) : (
          <>
            Already have an account?{' '}
            <button type="button" onClick={() => switchMode('login')}>
              Log in
            </button>
          </>
        )}
      </p>
    </div>
  )
}

export default LoginPage
