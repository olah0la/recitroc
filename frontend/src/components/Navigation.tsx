import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

function Navigation() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  return (
    <nav className="navigation">
      <div className="nav-container">
        <Link to="/" className="nav-logo">
          Recitroc
        </Link>
        <ul className="nav-links">
          <li>
            <Link to="/">Home</Link>
          </li>
          <li>
            <Link to="/swipe">Discover</Link>
          </li>
          <li>
            <Link to="/matches">Matches</Link>
          </li>
          <li>
            <Link to="/messages">Messages</Link>
          </li>
          {user ? (
            <li>
              <span className="nav-user">
                {user.username || user.first_name || user.email}
              </span>{' '}
              <button type="button" className="nav-logout" onClick={handleLogout}>
                Logout
              </button>
            </li>
          ) : (
            <li>
              <Link to="/login">Login</Link>
            </li>
          )}
          <li>
            <Link to="/about">About Us</Link>
          </li>
        </ul>
      </div>
    </nav>
  )
}

export default Navigation
