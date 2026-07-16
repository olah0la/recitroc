// Thin API client for the Recitroc backend.
//
// nginx-proxy routes /api → the FastAPI container, so the browser can use
// a same-origin relative URL: no CORS, no per-environment base URL.
const API_BASE = '/api/v1'

const TOKEN_KEY = 'recitroc_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

/** Shape of a user as returned by the backend (schemas/user.py UserRead).
 * The email is the primary key — there is no numeric id. */
export interface AuthUser {
  email: string
  username: string | null
  first_name: string | null
  last_name: string | null
  city: string | null
  country: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface SignupProfile {
  username?: string
  firstName?: string
  lastName?: string
}

export class ApiError extends Error {
  status: number

  constructor(status: number, detail: string) {
    super(detail)
    this.status = status
  }
}

// Central fetch wrapper: injects the bearer token when present and turns
// non-2xx responses into a typed ApiError carrying the backend's `detail`.
export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers)
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers })

  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      // Non-JSON error body; keep the status text.
    }
    throw new ApiError(response.status, detail)
  }

  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export async function signup(
  email: string,
  password: string,
  profile: SignupProfile = {},
): Promise<AuthUser> {
  return apiFetch<AuthUser>('/auth/signup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email,
      password,
      username: profile.username || null,
      first_name: profile.firstName || null,
      last_name: profile.lastName || null,
    }),
  })
}

export async function login(email: string, password: string): Promise<string> {
  // The OAuth2 password flow wants FORM fields, and names the identity
  // field "username" even though the backend treats it as an email.
  const form = new URLSearchParams({ username: email, password })
  const token = await apiFetch<{ access_token: string }>('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form,
  })
  return token.access_token
}

export async function fetchMe(): Promise<AuthUser> {
  return apiFetch<AuthUser>('/auth/me')
}

// --- postings ---------------------------------------------------------------

export type PostingKind = 'offer' | 'need'
export type PostingCategory = 'goods' | 'service'

/** Shape of a posting as returned by the backend (schemas/posting.py). */
export interface Posting {
  id: number
  owner_email: string
  kind: PostingKind
  category: PostingCategory
  title: string
  description: string | null
  tags: string[]
  city: string
  country: string | null
  latitude: number
  longitude: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface PostingInput {
  kind: PostingKind
  category: PostingCategory
  title: string
  description?: string
  tags?: string[]
  city: string
}

export async function createPosting(input: PostingInput): Promise<Posting> {
  return apiFetch<Posting>('/postings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export async function fetchMyPostings(kind?: PostingKind): Promise<Posting[]> {
  const query = kind ? `?kind=${kind}` : ''
  const page = await apiFetch<{ items: Posting[] }>(`/postings/mine${query}`)
  return page.items
}

/** A nearby posting carries its distance from the current user. */
export interface NearbyPosting extends Posting {
  distance_km: number
}

export async function fetchNearbyPostings(
  radiusKm = 10,
  kind?: PostingKind,
): Promise<NearbyPosting[]> {
  const params = new URLSearchParams({ radius_km: String(radiusKm) })
  if (kind) params.set('kind', kind)
  const page = await apiFetch<{ items: NearbyPosting[] }>(
    `/postings/nearby?${params}`,
  )
  return page.items
}

/** Set the user's home location from a city name (geocoded server-side). */
export async function setMyLocation(city: string): Promise<AuthUser> {
  return apiFetch<AuthUser>('/users/me/location', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ city }),
  })
}

// --- swipes -------------------------------------------------------------------

export type SwipeDirection = 'like' | 'pass'

export interface SwipeResult {
  matched: boolean
  match_id: number | null
}

/** The next nearby offers to swipe on (already-swiped ones never return). */
export async function fetchDeck(
  radiusKm = 10,
  limit = 10,
): Promise<NearbyPosting[]> {
  const params = new URLSearchParams({
    radius_km: String(radiusKm),
    limit: String(limit),
  })
  return apiFetch<NearbyPosting[]>(`/swipes/deck?${params}`)
}

export async function postSwipe(
  postingId: number,
  direction: SwipeDirection,
): Promise<SwipeResult> {
  return apiFetch<SwipeResult>('/swipes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ posting_id: postingId, direction }),
  })
}

/** Rewind: withdraw the verdict so the posting re-enters the deck. */
export async function deleteSwipe(postingId: number): Promise<void> {
  return apiFetch<void>(`/swipes/${postingId}`, { method: 'DELETE' })
}

// --- matches ------------------------------------------------------------------

export type MatchStatus = 'active' | 'archived'

/** A match, shaped from the current user's perspective by the backend. */
export interface Match {
  id: number
  status: MatchStatus
  created_at: string
  partner: AuthUser
  my_posting: Posting | null
  their_posting: Posting | null
}

export async function fetchMatches(): Promise<Match[]> {
  const page = await apiFetch<{ items: Match[] }>('/matches')
  return page.items
}
