import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { Box, Button, Flex, Text, VStack } from "@chakra-ui/react"
import { useAuth } from "../context/AuthContext"
import {
  ApiError,
  fetchMatches,
  type AuthUser,
  type Match,
  type Posting,
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

function emojiFor(posting: Posting | null): string {
  if (!posting) return "🤝"
  for (const tag of posting.tags) {
    const hit = TAG_EMOJI[tag.toLowerCase()]
    if (hit) return hit
  }
  return posting.category === "service" ? "🤝" : "📦"
}

function displayName(user: AuthUser): string {
  return user.username || user.first_name || user.email.split("@")[0]
}

function matchDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  })
}

type PageState = "loading" | "ready" | "unauthenticated" | "error"

function MatchesPage() {
  const [matches, setMatches] = useState<Match[]>([])
  const [state, setState] = useState<PageState>("loading")
  const { user, initializing } = useAuth()

  const loadMatches = useCallback(async () => {
    setState("loading")
    try {
      setMatches(await fetchMatches())
      setState("ready")
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setState("unauthenticated")
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
    loadMatches()
  }, [initializing, user, loadMatches])

  const emptyState = (
    <Flex
      direction="column"
      align="center"
      justify="center"
      minH="320px"
      gap="4"
      borderRadius="3xl"
      border="2px dashed"
      borderColor="gray.300"
      color="gray.500"
      textAlign="center"
      px="8"
    >
      {state === "loading" && <Text fontSize="lg">Loading your matches…</Text>}
      {state === "unauthenticated" && (
        <>
          <Text fontSize="52px">🔑</Text>
          <Text fontSize="lg" fontWeight="bold" color="gray.700">
            Log in to see your matches
          </Text>
          <Button as={Link} {...{ to: "/login" }} bg="#fd5068" color="white" borderRadius="full" px="6">
            Log in
          </Button>
        </>
      )}
      {state === "error" && (
        <>
          <Text fontSize="52px">😵</Text>
          <Text fontSize="lg" fontWeight="bold" color="gray.700">
            Something went wrong
          </Text>
          <Button onClick={loadMatches} bg="#fd5068" color="white" borderRadius="full" px="6">
            Try again
          </Button>
        </>
      )}
      {state === "ready" && (
        <>
          <Text fontSize="52px">💔</Text>
          <Text fontSize="lg" fontWeight="bold" color="gray.700">
            No matches yet
          </Text>
          <Text fontSize="sm">
            When you and another trader like each other's offers, they show up
            here.
          </Text>
          <Button
            as={Link}
            {...{ to: "/swipe" }}
            bg="#fd5068"
            color="white"
            borderRadius="full"
            px="6"
            _hover={{ bg: "#e63e57" }}
          >
            Keep swiping
          </Button>
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
          💞 Matches
        </Text>
        <Text color="gray.500" fontSize="sm">
          Traders who liked you back
        </Text>
      </VStack>

      <VStack gap="4" w="min(560px, 92vw)">
        {state !== "ready" || matches.length === 0
          ? emptyState
          : matches.map((match) => <MatchRow key={match.id} match={match} />)}
      </VStack>
    </Flex>
  )
}

// One match: who, when, and the two postings that sparked it.
function MatchRow({ match }: { match: Match }) {
  return (
    <Flex
      w="100%"
      align="center"
      gap="4"
      p="4"
      bg="white"
      borderRadius="2xl"
      boxShadow="0 4px 14px rgba(0,0,0,0.08)"
    >
      <Flex
        align="center"
        justify="center"
        flexShrink={0}
        w="64px"
        h="64px"
        fontSize="32px"
        borderRadius="full"
        background={GRADIENTS[match.id % GRADIENTS.length]}
      >
        {emojiFor(match.their_posting)}
      </Flex>
      <Box flex="1" minW="0">
        <Flex align="baseline" gap="2">
          <Text fontWeight="bold" color="gray.800">
            {displayName(match.partner)}
          </Text>
          <Text fontSize="xs" color="gray.400">
            matched {matchDate(match.created_at)}
          </Text>
        </Flex>
        {/* A posting may be null if it was deleted — the match lives on. */}
        <Text fontSize="sm" color="gray.600" lineClamp={2}>
          {match.their_posting
            ? `They offer: ${match.their_posting.title}`
            : "Their posting is gone"}
          {" · "}
          {match.my_posting
            ? `You offer: ${match.my_posting.title}`
            : "your posting is gone"}
        </Text>
      </Box>
      {/* Messaging lands with RT-6; until then this is a teaser. */}
      <Button size="sm" borderRadius="full" px="4" variant="outline" disabled>
        Say hi (soon)
      </Button>
    </Flex>
  )
}

export default MatchesPage
