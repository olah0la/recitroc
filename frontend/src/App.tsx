import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Navigation from './components/Navigation'
import HomePage from './pages/HomePage'
import LoginPage from './pages/LoginPage'
import AboutPage from './pages/AboutPage'
import MessagesPage from './pages/MessagesPage'

function App() {
  return (
    <Router>
      <div className="app">
        <Navigation />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/about" element={<AboutPage />} />
            <Route path="/messages" element={<MessagesPage />} />
          </Routes>
        </main>
      </div>
    </Router>
  )
}

export default App
