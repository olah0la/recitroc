// Shared presentation helpers: how a posting/user is rendered as visuals
// (emoji, gradient, display name) across SwipePage, MatchesPage and
// MessagesPage. Postings have no photos yet, so the emoji IS the artwork.
import type { AuthUser, Posting } from '../services/api'

export const GRADIENTS = [
  'linear-gradient(135deg, #f6d365 0%, #fda085 100%)',
  'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
  'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  'linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%)',
  'linear-gradient(135deg, #30cfd0 0%, #330867 100%)',
  'linear-gradient(135deg, #96e6a1 0%, #d4fc79 100%)',
]

/** Stable per-id gradient so the same posting/match always looks the same. */
export function gradientFor(id: number): string {
  return GRADIENTS[id % GRADIENTS.length]
}

const TAG_EMOJI: Record<string, string> = {
  kitchen: '☕',
  coffee: '☕',
  music: '🎸',
  instruments: '🎸',
  outdoors: '🚲',
  sports: '🚲',
  bike: '🚲',
  plants: '🪴',
  games: '🎲',
  books: '📚',
  electronics: '📷',
}

export function emojiFor(
  posting: Pick<Posting, 'tags' | 'category'> | null,
): string {
  if (!posting) return '🤝'
  for (const tag of posting.tags) {
    const hit = TAG_EMOJI[tag.toLowerCase()]
    if (hit) return hit
  }
  return posting.category === 'service' ? '🤝' : '📦'
}

/** Best available human name: username, first name, or the email's local part. */
export function displayName(user: AuthUser): string {
  return user.username || user.first_name || user.email.split('@')[0]
}
