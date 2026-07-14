import { useCallback, useEffect, useRef, useState } from "react"
import { Link } from "react-router-dom"
import { Box, Button, Flex, Text, VStack } from "@chakra-ui/react"
import {
  SwipeCard,
  type SwipeCardHandle,
  type SwipeItem,
} from "../components/SwipeCard"
import { useAuth } from "../context/AuthContext"
import {
  ApiError,
  deleteSwipe,
  fetchDeck,
  postSwipe,
  type NearbyPosting,
} from "../services/api"

const GRADIENTS = [
  "linear-gradient(135deg, #f6d365 0%, #fda085 100%)",
  "linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)",
  "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
  "linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%)",
  "linear-gradient(135deg, #30cfd0 0%, #330867 100%)",
  "linear-gradient(135deg, #96e6a1 0%, #d4fc79 100%)",
]

const TAG_EMOJI: Record<string, string> = {
  kitchen: "☕",
  coffee: "☕",
  music: "🎸",
  instruments: "🎸",
  outdoors: "🚲",
  sports: "🚲",
  bike: "🚲",
  plants: "🪴",
  games: "🎲",
  books: "📚",
  electronics: "📷",
}

function emojiFor(posting: NearbyPosting): string {
  for (const tag of posting.tags) {
    const hit = TAG_EMOJI[tag.toLowerCase()]
    if (hit) return hit
  }
  return posting.category === "service" ? "🤝" : "📦"
}

function toSwipeItem(posting: NearbyPosting): SwipeItem {
  return {
    id: String(posting.id),
    title: posting.title,
    // Only the email is public for now; show its local part as the name.
    owner: posting.owner_email.split("@")[0],
    distance: `${posting.distance_km} km away`,
    description: posting.description ?? "",
    emoji: emojiFor(posting),
    gradient: GRADIENTS[posting.id % GRADIENTS.length],
    tags: posting.tags,
  }
}

type DeckState = "loading" | "ready" | "unauthenticated" | "no-location" | "error"

function SwipePage() {
  const [cards, setCards] = useState<NearbyPosting[]>([])
  const [history, setHistory] = useState<NearbyPosting[]>([])
  const [likes, setLikes] = useState(0)
  const [match, setMatch] = useState<SwipeItem | null>(null)
  const [state, setState] = useState<DeckState>("loading")
  const [radiusKm, setRadiusKm] = useState(10)
  const { user, initializing } = useAuth()
  const topRef = useRef<SwipeCardHandle>(null)

  const loadDeck = useCallback(async (radius: number) => {
    setState("loading")
    try {
      setCards(await fetchDeck(radius, 10))
      setState("ready")
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setState("unauthenticated")
      } else if (err instanceof ApiError && err.status === 409) {
        setState("no-location")
      } else {
        setState("error")
      }
    }
  }, [])

  useEffect(() => {
    if (initializing) return
    if (!user) {
      setState("unauthenticated")
      return
    }
    loadDeck(radiusKm)
  }, [initializing, user, radiusKm, loadDeck])

  const handleSwipe = (dir: "left" | "right", item: SwipeItem) => {
    const posting = cards.find((c) => String(c.id) === item.id)
    if (!posting) return
    setHistory((h) => [...h, posting])
    setCards((c) => c.filter((p) => p.id !== posting.id))
    if (dir === "right") setLikes((n) => n + 1)
    // Persist the verdict; the response says whether it made a match.
    postSwipe(posting.id, dir === "right" ? "like" : "pass")
      .then((result) => {
        if (result.matched) setMatch(item)
      })
      .catch(() => {
        // The optimistic UI already advanced; a rewind re-syncs if needed.
      })
  }

  const trigger = (dir: "left" | "right") => topRef.current?.swipe(dir)

  const rewind = async () => {
    const last = history[history.length - 1]
    if (!last) return
    try {
      await deleteSwipe(last.id)
    } catch {
      // Verdict already gone server-side; restoring the card is still right.
    }
    setHistory((h) => h.slice(0, -1))
    setCards((c) => [last, ...c])
  }

  const widenSearch = () => setRadiusKm((r) => Math.min(r * 2, 500))

  const visible = cards.slice(0, 3)

  const emptyState = (
    <Flex
      direction="column"
      align="center"
      justify="center"
      h="100%"
      gap="4"
      borderRadius="3xl"
      border="2px dashed"
      borderColor="gray.300"
      color="gray.500"
      textAlign="center"
      px="8"
    >
      {state === "loading" && <Text fontSize="lg">Loading nearby offers…</Text>}
      {state === "unauthenticated" && (
        <>
          <Text fontSize="52px">🔑</Text>
          <Text fontSize="lg" fontWeight="bold" color="gray.700">
            Log in to start swiping
          </Text>
          <Button as={Link} {...{ to: "/login" }} bg="#fd5068" color="white" borderRadius="full" px="6">
            Log in
          </Button>
        </>
      )}
      {state === "no-location" && (
        <>
          <Text fontSize="52px">📍</Text>
          <Text fontSize="lg" fontWeight="bold" color="gray.700">
            Where are you?
          </Text>
          <Text fontSize="sm">
            Set your city so we can find offers near you.
          </Text>
          <Button as={Link} {...{ to: "/onboarding" }} bg="#fd5068" color="white" borderRadius="full" px="6">
            Complete your profile
          </Button>
        </>
      )}
      {state === "error" && (
        <>
          <Text fontSize="52px">😵</Text>
          <Text fontSize="lg" fontWeight="bold" color="gray.700">
            Something went wrong
          </Text>
          <Button onClick={() => loadDeck(radiusKm)} bg="#fd5068" color="white" borderRadius="full" px="6">
            Try again
          </Button>
        </>
      )}
      {state === "ready" && (
        <>
          <Text fontSize="52px">🎉</Text>
          <Text fontSize="lg" fontWeight="bold" color="gray.700">
            You're all caught up!
          </Text>
          <Text fontSize="sm">
            No more offers within {radiusKm} km. Widen the search or check
            back soon.
          </Text>
          <Flex gap="3">
            {radiusKm < 500 && (
              <Button onClick={widenSearch} bg="#fd5068" color="white" borderRadius="full" px="6" _hover={{ bg: "#e63e57" }}>
                Search wider ({Math.min(radiusKm * 2, 500)} km)
              </Button>
            )}
            <Button onClick={() => loadDeck(radiusKm)} variant="outline" borderRadius="full" px="6">
              Check again
            </Button>
          </Flex>
        </>
      )}
    </Flex>
  )

  return (
    <Flex direction="column" align="center" gap="6" py="4">
      {/* Header */}
      <VStack gap="1">
        <Text
          fontSize="3xl"
          fontWeight="extrabold"
          bgGradient="linear-gradient(to right, #fd5068, #fe8c68)"
          bgClip="text"
        >
          🔥 recitroc
        </Text>
        <Text color="gray.500" fontSize="sm">
          Swipe right to trade · {likes} liked · within {radiusKm} km
        </Text>
      </VStack>

      {/* Card deck */}
      <Box position="relative" w="340px" h="480px">
        {visible.length === 0
          ? emptyState
          : // Render bottom-to-top so the top card paints last.
            [...visible].reverse().map((posting) => {
              const offset = cards.indexOf(posting)
              return (
                <SwipeCard
                  key={posting.id}
                  ref={offset === 0 ? topRef : undefined}
                  item={toSwipeItem(posting)}
                  active={offset === 0}
                  offset={offset}
                  onSwipe={handleSwipe}
                />
              )
            })}
      </Box>

      {/* Action buttons */}
      {visible.length > 0 && (
        <Flex align="center" gap="4">
          <ActionButton
            label="Rewind"
            color="#fbbf24"
            size="46px"
            fontSize="18px"
            onClick={rewind}
          >
            ↺
          </ActionButton>
          <ActionButton label="Nope" color="#fd5068" onClick={() => trigger("left")}>
            ✕
          </ActionButton>
          <ActionButton label="Like" color="#22c55e" onClick={() => trigger("right")}>
            ♥
          </ActionButton>
        </Flex>
      )}

      {/* Match overlay */}
      {match && (
        <Flex
          position="fixed"
          inset="0"
          zIndex={1000}
          align="center"
          justify="center"
          bg="rgba(0,0,0,0.6)"
          onClick={() => setMatch(null)}
        >
          <VStack
            gap="4"
            p="8"
            borderRadius="2xl"
            bg="white"
            maxW="320px"
            textAlign="center"
            onClick={(e) => e.stopPropagation()}
          >
            <Text
              fontSize="3xl"
              fontWeight="extrabold"
              bgGradient="linear-gradient(to right, #fd5068, #fe8c68)"
              bgClip="text"
            >
              It's a Match!
            </Text>
            <Flex
              align="center"
              justify="center"
              w="120px"
              h="120px"
              fontSize="64px"
              borderRadius="full"
              background={match.gradient}
            >
              {match.emoji}
            </Flex>
            <Text color="gray.600">
              You and {match.owner} both want to trade the <b>{match.title}</b>.
            </Text>
            <Button
              onClick={() => setMatch(null)}
              bg="#fd5068"
              color="white"
              borderRadius="full"
              px="8"
              w="100%"
              _hover={{ bg: "#e63e57" }}
            >
              Keep swiping
            </Button>
          </VStack>
        </Flex>
      )}
    </Flex>
  )
}

// Circular action button used in the control bar.
function ActionButton({
  label,
  color,
  size = "56px",
  fontSize = "24px",
  onClick,
  children,
}: {
  label: string
  color: string
  size?: string
  fontSize?: string
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <Flex
      as="button"
      aria-label={label}
      onClick={onClick}
      align="center"
      justify="center"
      w={size}
      h={size}
      fontSize={fontSize}
      borderRadius="full"
      bg="white"
      color={color}
      boxShadow="0 6px 16px rgba(0,0,0,0.15)"
      cursor="pointer"
      transition="transform 0.15s ease, box-shadow 0.15s ease"
      _hover={{ transform: "translateY(-3px)", boxShadow: "0 10px 22px rgba(0,0,0,0.2)" }}
      _active={{ transform: "scale(0.92)" }}
    >
      {children}
    </Flex>
  )
}

export default SwipePage
