import { useState, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import {
  createPosting,
  setMyLocation,
  type PostingCategory,
  type PostingKind,
} from '../services/api'

// Two-step onboarding: first what you NEED from the community, then what
// you can OFFER it. Each step creates one posting; both steps are
// skippable — more postings can always be added later.
const STEPS: {
  kind: PostingKind
  heading: string
  blurb: string
  titlePlaceholder: string
}[] = [
  {
    kind: 'need',
    heading: 'What do you need?',
    blurb: 'A service like language exchange, or goods like a bike or a sofa — what would help you right now?',
    titlePlaceholder: 'e.g. Spanish conversation practice',
  },
  {
    kind: 'offer',
    heading: 'What can you offer?',
    blurb: 'What could you give back to the community — things you no longer use, or something you are good at?',
    titlePlaceholder: 'e.g. Bicycle repair',
  },
]

function OnboardingPage() {
  const [step, setStep] = useState(0)
  const [category, setCategory] = useState<PostingCategory>('goods')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [tags, setTags] = useState('')
  const [city, setCity] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [locationSet, setLocationSet] = useState(false)
  const { user, initializing } = useAuth()
  const navigate = useNavigate()

  if (!initializing && !user) {
    navigate('/login')
    return null
  }

  const current = STEPS[step]

  const advance = () => {
    if (step + 1 < STEPS.length) {
      // Keep the city (it rarely changes between steps), reset the rest.
      setStep(step + 1)
      setCategory('goods')
      setTitle('')
      setDescription('')
      setTags('')
      setError(null)
    } else {
      navigate('/swipe')
    }
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await createPosting({
        kind: current.kind,
        category,
        title,
        description: description || undefined,
        tags: tags
          .split(',')
          .map((t) => t.trim())
          .filter(Boolean),
        city,
      })
      // The first saved posting also pins the user's home location, which
      // the nearby feed requires. Best-effort: a failure here shouldn't
      // block onboarding.
      if (!locationSet && !user?.city) {
        try {
          await setMyLocation(city)
          setLocationSet(true)
        } catch {
          // ignore — the user can set a location later
        }
      }
      advance()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="page">
      <p className="onboarding-progress">
        Step {step + 1} of {STEPS.length}
      </p>
      <h1>{current.heading}</h1>
      <p className="onboarding-blurb">{current.blurb}</p>
      <form onSubmit={handleSubmit} className="login-form">
        <div className="form-group">
          <span className="category-label">This is:</span>
          <label className="category-choice">
            <input
              type="radio"
              name="category"
              checked={category === 'goods'}
              onChange={() => setCategory('goods')}
            />{' '}
            Goods
          </label>
          <label className="category-choice">
            <input
              type="radio"
              name="category"
              checked={category === 'service'}
              onChange={() => setCategory('service')}
            />{' '}
            A service
          </label>
        </div>
        <div className="form-group">
          <label htmlFor="title">Title:</label>
          <input
            type="text"
            id="title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder={current.titlePlaceholder}
            required
            maxLength={200}
          />
        </div>
        <div className="form-group">
          <label htmlFor="description">Description (optional):</label>
          <input
            type="text"
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>
        <div className="form-group">
          <label htmlFor="tags">Tags (comma-separated, optional):</label>
          <input
            type="text"
            id="tags"
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            placeholder="e.g. outdoors, sports"
          />
        </div>
        <div className="form-group">
          <label htmlFor="city">City:</label>
          <input
            type="text"
            id="city"
            value={city}
            onChange={(e) => setCity(e.target.value)}
            required
            maxLength={120}
          />
        </div>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" disabled={submitting}>
          {submitting ? 'Saving…' : step + 1 < STEPS.length ? 'Save & continue' : 'Save & finish'}
        </button>
      </form>
      <p className="form-switch">
        <button type="button" onClick={advance}>
          Skip this step
        </button>
      </p>
    </div>
  )
}

export default OnboardingPage
