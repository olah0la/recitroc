import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Navigation from './components/Navigation'
import HomePage from './pages/HomePage'
import LoginPage from './pages/LoginPage'
import AboutPage from './pages/AboutPage'
import MatchesPage from './pages/MatchesPage'
import MessagesPage from './pages/MessagesPage'
import OnboardingPage from './pages/OnboardingPage'
import SwipePage from './pages/SwipePage'

function App() {
  return (
    <Router>
      <div className="app">
        <Navigation />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/swipe" element={<SwipePage />} />
            <Route path="/matches" element={<MatchesPage />} />
            <Route path="/onboarding" element={<OnboardingPage />} />
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
