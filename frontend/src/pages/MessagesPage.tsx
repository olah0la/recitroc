import { useCallback, useEffect, useRef, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { Box, Button, Flex, Input, Text, VStack } from "@chakra-ui/react"
import { useAuth } from "../context/AuthContext"
import { displayName, emojiFor, gradientFor } from "../lib/display"
import {
  ApiError,
  fetchMatches,
  fetchMessages,
  markMessagesRead,
  sendMessage,
  type Match,
  type Message,
} from "../services/api"

// How often the open thread asks "anything after my last id?". REST +
// polling is v1; a WebSocket push channel is a planned follow-up.
const POLL_MS = 4000

type PageState = "loading" | "ready" | "unauthenticated" | "error"

function MessagesPage() {
  const [matches, setMatches] = useState<Match[]>([])
  const [state, setState] = useState<PageState>("loading")
  const [params, setParams] = useSearchParams()
  const { user, initializing } = useAuth()

  const selectedId = Number(params.get("match")) || null
  const selected = matches.find((m) => m.id === selectedId) ?? null

  const loadMatches = useCallback(async () => {
    try {
      const items = await fetchMatches()
      setMatches(items)
      setState("ready")
      return items
    } catch (err) {
      setState(
        err instanceof ApiError && err.status === 401
          ? "unauthenticated"
          : "error",
      )
      return []
    }
  }, [])

  useEffect(() => {
    if (initializing) return
    if (!user) {
      setState("unauthenticated")
      return
    }
    loadMatches().then((items) => {
      // Deep link ?match= wins; otherwise open the first conversation.
      if (!params.get("match") && items.length > 0) {
        setParams({ match: String(items[0].id) }, { replace: true })
      }
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initializing, user, loadMatches])

  // The open thread never shows a badge — covers both clicking a match
  // and arriving via a ?match= deep link. The server learns it's read
  // from the thread pane's markMessagesRead call.
  useEffect(() => {
    if (selectedId === null) return
    setMatches((all) => {
      // Same reference when nothing changes, so React bails out and this
      // effect doesn't re-fire forever.
      if (!all.some((m) => m.id === selectedId && m.unread_count > 0)) {
        return all
      }
      return all.map((m) =>
        m.id === selectedId ? { ...m, unread_count: 0 } : m,
      )
    })
  }, [selectedId, matches])

  const select = (id: number) => setParams({ match: String(id) })

  if (state !== "ready" || matches.length === 0) {
    return (
      <Flex direction="column" align="center" gap="6" py="4">
        <Header />
        <EmptyState state={state} />
      </Flex>
    )
  }

  return (
    <Flex direction="column" align="center" gap="6" py="4">
      <Header />
      <Flex
        w="min(860px, 94vw)"
        h="560px"
        bg="white"
        borderRadius="2xl"
        boxShadow="0 4px 14px rgba(0,0,0,0.08)"
        overflow="hidden"
      >
        {/* Match list pane */}
        <VStack
          w="280px"
          flexShrink={0}
          align="stretch"
          gap="0"
          overflowY="auto"
          borderRight="1px solid"
          borderColor="gray.100"
        >
          {matches.map((match) => (
            <MatchListRow
              key={match.id}
              match={match}
              active={match.id === selectedId}
              onSelect={() => select(match.id)}
            />
          ))}
        </VStack>

        {/* Conversation pane */}
        {selected && user ? (
          <Thread key={selected.id} match={selected} myEmail={user.email} />
        ) : (
          <Flex flex="1" align="center" justify="center" color="gray.400">
            <Text>Pick a match to start chatting</Text>
          </Flex>
        )}
      </Flex>
    </Flex>
  )
}

function Header() {
  return (
    <VStack gap="1">
      <Text
        fontSize="3xl"
        fontWeight="extrabold"
        bgGradient="linear-gradient(to right, #fd5068, #fe8c68)"
        bgClip="text"
      >
        💬 Messages
      </Text>
      <Text color="gray.500" fontSize="sm">
        Talk it out, work out the trade
      </Text>
    </VStack>
  )
}

function EmptyState({ state }: { state: PageState }) {
  return (
    <Flex
      direction="column"
      align="center"
      justify="center"
      minH="320px"
      w="min(560px, 92vw)"
      gap="4"
      borderRadius="3xl"
      border="2px dashed"
      borderColor="gray.300"
      color="gray.500"
      textAlign="center"
      px="8"
    >
      {state === "loading" && <Text fontSize="lg">Loading conversations…</Text>}
      {state === "unauthenticated" && (
        <>
          <Text fontSize="52px">🔑</Text>
          <Text fontSize="lg" fontWeight="bold" color="gray.700">
            Log in to see your messages
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
          <Button onClick={() => window.location.reload()} bg="#fd5068" color="white" borderRadius="full" px="6">
            Try again
          </Button>
        </>
      )}
      {state === "ready" && (
        <>
          <Text fontSize="52px">💬</Text>
          <Text fontSize="lg" fontWeight="bold" color="gray.700">
            No conversations yet
          </Text>
          <Text fontSize="sm">Chat opens up once you match with someone.</Text>
          <Button
            as={Link}
            {...{ to: "/swipe" }}
            bg="#fd5068"
            color="white"
            borderRadius="full"
            px="6"
            _hover={{ bg: "#e63e57" }}
          >
            Go swipe
          </Button>
        </>
      )}
    </Flex>
  )
}

function MatchListRow({
  match,
  active,
  onSelect,
}: {
  match: Match
  active: boolean
  onSelect: () => void
}) {
  const preview = match.last_message
    ? match.last_message.body
    : "Say hi and start the trade!"
  return (
    <Flex
      as="button"
      onClick={onSelect}
      align="center"
      gap="3"
      px="4"
      py="3"
      textAlign="left"
      bg={active ? "#fff0f2" : "transparent"}
      _hover={{ bg: active ? "#fff0f2" : "gray.50" }}
      cursor="pointer"
    >
      <Flex
        align="center"
        justify="center"
        flexShrink={0}
        w="44px"
        h="44px"
        fontSize="22px"
        borderRadius="full"
        background={gradientFor(match.id)}
      >
        {emojiFor(match.their_posting)}
      </Flex>
      <Box flex="1" minW="0">
        <Text fontWeight="bold" fontSize="sm" color="gray.800" truncate>
          {displayName(match.partner)}
        </Text>
        <Text fontSize="xs" color="gray.500" truncate>
          {preview}
        </Text>
      </Box>
      {match.unread_count > 0 && (
        <Flex
          align="center"
          justify="center"
          minW="20px"
          h="20px"
          px="1.5"
          fontSize="xs"
          fontWeight="bold"
          color="white"
          bg="#fd5068"
          borderRadius="full"
        >
          {match.unread_count}
        </Flex>
      )}
    </Flex>
  )
}

// One open conversation. Keyed by match id in the parent, so switching
// matches remounts it with clean state — no cross-thread bleed.
function Thread({ match, myEmail }: { match: Match; myEmail: string }) {
  const [messages, setMessages] = useState<Message[]>([])
  const [draft, setDraft] = useState("")
  const [loading, setLoading] = useState(true)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Append new messages, dropping any we already have (the optimistic
  // append and the poll can both deliver the same message).
  const merge = useCallback((incoming: Message[]) => {
    if (incoming.length === 0) return
    setMessages((existing) => {
      const known = new Set(existing.map((m) => m.id))
      return [...existing, ...incoming.filter((m) => !known.has(m.id))]
    })
  }, [])

  useEffect(() => {
    let cancelled = false
    let lastId = 0

    const poll = async () => {
      try {
        const newer = await fetchMessages(match.id, lastId)
        if (cancelled || newer.length === 0) return
        lastId = newer[newer.length - 1].id
        merge(newer)
        // Whatever just arrived is on screen — tell the server it's read.
        markMessagesRead(match.id).catch(() => {})
      } catch {
        // Transient poll failure: keep the interval, next tick retries.
      }
    }

    poll().finally(() => !cancelled && setLoading(false))
    const timer = setInterval(poll, POLL_MS)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [match.id, merge])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages.length])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    const body = draft.trim()
    if (!body) return
    setDraft("")
    try {
      merge([await sendMessage(match.id, body)])
    } catch {
      setDraft(body) // hand the text back rather than losing it
    }
  }

  return (
    <Flex direction="column" flex="1" minW="0">
      {/* Thread header */}
      <Flex align="center" gap="3" px="5" py="3" borderBottom="1px solid" borderColor="gray.100">
        <Flex
          align="center"
          justify="center"
          w="36px"
          h="36px"
          fontSize="18px"
          borderRadius="full"
          background={gradientFor(match.id)}
        >
          {emojiFor(match.their_posting)}
        </Flex>
        <Box>
          <Text fontWeight="bold" fontSize="sm" color="gray.800">
            {displayName(match.partner)}
          </Text>
          <Text fontSize="xs" color="gray.500">
            {match.their_posting
              ? `Trading: ${match.their_posting.title}`
              : "Their posting is gone — the match lives on"}
          </Text>
        </Box>
      </Flex>

      {/* Message stream */}
      <VStack flex="1" align="stretch" gap="2" px="5" py="4" overflowY="auto" bg="gray.50">
        {loading && (
          <Text fontSize="sm" color="gray.400" textAlign="center">
            Loading…
          </Text>
        )}
        {!loading && messages.length === 0 && (
          <Text fontSize="sm" color="gray.400" textAlign="center" mt="8">
            No messages yet — break the ice! 🧊
          </Text>
        )}
        {messages.map((message) => {
          const mine = message.sender_email === myEmail
          return (
            <Flex key={message.id} justify={mine ? "flex-end" : "flex-start"}>
              <Box
                maxW="70%"
                px="3.5"
                py="2"
                fontSize="sm"
                borderRadius="2xl"
                bg={mine ? "#fd5068" : "white"}
                color={mine ? "white" : "gray.800"}
                boxShadow="0 1px 3px rgba(0,0,0,0.08)"
                borderBottomRightRadius={mine ? "sm" : "2xl"}
                borderBottomLeftRadius={mine ? "2xl" : "sm"}
              >
                {message.body}
              </Box>
            </Flex>
          )
        })}
        <div ref={bottomRef} />
      </VStack>

      {/* Composer */}
      <Flex as="form" onSubmit={submit} gap="2" px="4" py="3" borderTop="1px solid" borderColor="gray.100">
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={`Message ${displayName(match.partner)}…`}
          maxLength={2000}
          borderRadius="full"
          bg="gray.50"
        />
        <Button
          type="submit"
          disabled={!draft.trim()}
          bg="#fd5068"
          color="white"
          borderRadius="full"
          px="6"
          _hover={{ bg: "#e63e57" }}
        >
          Send
        </Button>
      </Flex>
    </Flex>
  )
}

export default MessagesPage
