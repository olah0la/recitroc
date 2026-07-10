import { useRef, useState } from "react"
import { Box, Button, Flex, Text, VStack } from "@chakra-ui/react"
import {
  SwipeCard,
  type SwipeCardHandle,
  type SwipeItem,
} from "../components/SwipeCard"

const DECK: SwipeItem[] = [
  {
    id: "1",
    title: "Vintage Film Camera",
    owner: "Maya",
    distance: "1.2 km away",
    description: "Canon AE-1, fully working. Looking to swap for vinyl records.",
    emoji: "📷",
    gradient: "linear-gradient(135deg, #f6d365 0%, #fda085 100%)",
    tags: ["Electronics", "Retro", "Trade"],
  },
  {
    id: "2",
    title: "Mountain Bike",
    owner: "Leo",
    distance: "3.4 km away",
    description: "27-speed hardtail, barely used. Open to camping gear.",
    emoji: "🚲",
    gradient: "linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)",
    tags: ["Outdoors", "Sports"],
  },
  {
    id: "3",
    title: "Acoustic Guitar",
    owner: "Sofia",
    distance: "0.8 km away",
    description: "Yamaha dreadnought with case. Would love a keyboard.",
    emoji: "🎸",
    gradient: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
    tags: ["Music", "Instruments"],
  },
  {
    id: "4",
    title: "Espresso Machine",
    owner: "Noah",
    distance: "2.1 km away",
    description: "Barista-grade, descaled monthly. Swap for a stand mixer?",
    emoji: "☕",
    gradient: "linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%)",
    tags: ["Kitchen", "Coffee"],
  },
  {
    id: "5",
    title: "Board Game Bundle",
    owner: "Ava",
    distance: "4.7 km away",
    description: "Catan, Ticket to Ride & more. Trading for books.",
    emoji: "🎲",
    gradient: "linear-gradient(135deg, #30cfd0 0%, #330867 100%)",
    tags: ["Games", "Bundle"],
  },
  {
    id: "6",
    title: "Succulent Collection",
    owner: "Kai",
    distance: "1.9 km away",
    description: "Six potted plants ready for a new home. Any craft supplies!",
    emoji: "🪴",
    gradient: "linear-gradient(135deg, #96e6a1 0%, #d4fc79 100%)",
    tags: ["Plants", "Home"],
  },
]

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

function SwipePage() {
  const [remaining, setRemaining] = useState<SwipeItem[]>(DECK)
  const [history, setHistory] = useState<SwipeItem[]>([])
  const [likes, setLikes] = useState(0)
  const [match, setMatch] = useState<SwipeItem | null>(null)
  const topRef = useRef<SwipeCardHandle>(null)

  const handleSwipe = (dir: "left" | "right", item: SwipeItem) => {
    setHistory((h) => [...h, item])
    setRemaining((r) => r.filter((c) => c.id !== item.id))
    if (dir === "right") {
      setLikes((n) => n + 1)
      // Roughly a third of likes turn into a match.
      if (Math.random() < 0.4) setMatch(item)
    }
  }

  const trigger = (dir: "left" | "right") => topRef.current?.swipe(dir)

  const rewind = () => {
    setHistory((h) => {
      if (h.length === 0) return h
      const last = h[h.length - 1]
      setRemaining((r) => [last, ...r])
      return h.slice(0, -1)
    })
  }

  const reset = () => {
    setRemaining(DECK)
    setHistory([])
    setLikes(0)
    setMatch(null)
  }

  const visible = remaining.slice(0, 3)

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
          Swipe right to trade · {likes} liked
        </Text>
      </VStack>

      {/* Card deck */}
      <Box position="relative" w="340px" h="480px">
        {visible.length === 0 ? (
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
            <Text fontSize="52px">🎉</Text>
            <Text fontSize="lg" fontWeight="bold" color="gray.700">
              You're all caught up!
            </Text>
            <Text fontSize="sm">
              No more items nearby. Check back soon or start over.
            </Text>
            <Button
              onClick={reset}
              bg="#fd5068"
              color="white"
              borderRadius="full"
              px="6"
              _hover={{ bg: "#e63e57" }}
            >
              Start over
            </Button>
          </Flex>
        ) : (
          // Render bottom-to-top so the top card paints last.
          [...visible].reverse().map((item) => {
            const offset = remaining.indexOf(item)
            return (
              <SwipeCard
                key={item.id}
                ref={offset === 0 ? topRef : undefined}
                item={item}
                active={offset === 0}
                offset={offset}
                onSwipe={handleSwipe}
              />
            )
          })
        )}
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
          <ActionButton
            label="Super like"
            color="#38bdf8"
            size="46px"
            fontSize="18px"
            onClick={() => trigger("right")}
          >
            ★
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
              You and {match.owner} both want to trade the{" "}
              <b>{match.title}</b>.
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

export default SwipePage
