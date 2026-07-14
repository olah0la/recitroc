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

/** Shape of a user as returned by the backend (schemas/user.py UserRead). */
export interface AuthUser {
  id: number
  email: string
  full_name: string | null
  is_active: boolean
  created_at: string
  updated_at: string
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
  fullName?: string,
): Promise<AuthUser> {
  return apiFetch<AuthUser>('/auth/signup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, full_name: fullName || null }),
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
