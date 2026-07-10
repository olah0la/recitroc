import {
  forwardRef,
  useImperativeHandle,
  useRef,
  useState,
  type PointerEvent,
} from "react"
import { Badge, Box, Flex, HStack, Text } from "@chakra-ui/react"

export type SwipeItem = {
  id: string
  title: string
  owner: string
  distance: string
  description: string
  emoji: string
  gradient: string
  tags: string[]
}

export type SwipeCardHandle = {
  swipe: (dir: "left" | "right") => void
}

type SwipeCardProps = {
  item: SwipeItem
  /** Only the top card of the deck is interactive. */
  active: boolean
  /** Depth in the stack (0 = top) used for the peeking effect. */
  offset: number
  onSwipe: (dir: "left" | "right", item: SwipeItem) => void
}

const SWIPE_THRESHOLD = 120

export const SwipeCard = forwardRef<SwipeCardHandle, SwipeCardProps>(
  function SwipeCard({ item, active, offset, onSwipe }, ref) {
    const [drag, setDrag] = useState({ x: 0, y: 0 })
    const [animating, setAnimating] = useState(false)
    const start = useRef<{ x: number; y: number } | null>(null)

    const fling = (dir: "left" | "right") => {
      setAnimating(true)
      setDrag({ x: dir === "right" ? 1100 : -1100, y: 40 })
      window.setTimeout(() => onSwipe(dir, item), 280)
    }

    useImperativeHandle(ref, () => ({ swipe: fling }), [item])

    const handlePointerDown = (e: PointerEvent<HTMLDivElement>) => {
      if (!active) return
      start.current = { x: e.clientX, y: e.clientY }
      setAnimating(false)
      e.currentTarget.setPointerCapture(e.pointerId)
    }

    const handlePointerMove = (e: PointerEvent<HTMLDivElement>) => {
      if (!start.current) return
      setDrag({
        x: e.clientX - start.current.x,
        y: e.clientY - start.current.y,
      })
    }

    const handlePointerUp = () => {
      if (!start.current) return
      start.current = null
      if (drag.x > SWIPE_THRESHOLD) fling("right")
      else if (drag.x < -SWIPE_THRESHOLD) fling("left")
      else {
        setAnimating(true)
        setDrag({ x: 0, y: 0 })
      }
    }

    const rotate = drag.x / 18
    const likeOpacity = Math.max(0, Math.min(1, drag.x / 100))
    const nopeOpacity = Math.max(0, Math.min(1, -drag.x / 100))

    // Cards behind the top one peek out slightly, scaled down.
    const restingTransform = `translateY(${offset * 14}px) scale(${
      1 - offset * 0.05
    })`
    const activeTransform = `translate(${drag.x}px, ${drag.y}px) rotate(${rotate}deg)`

    return (
      <Box
        position="absolute"
        top="0"
        left="0"
        w="100%"
        h="100%"
        userSelect="none"
        touchAction="none"
        borderRadius="3xl"
        overflow="hidden"
        boxShadow="0 18px 45px rgba(0,0,0,0.22)"
        background={item.gradient}
        cursor={active ? "grab" : "default"}
        zIndex={100 - offset}
        transform={active ? activeTransform : restingTransform}
        transition={
          animating || !active
            ? "transform 0.3s cubic-bezier(0.22, 1, 0.36, 1)"
            : "none"
        }
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        _active={{ cursor: active ? "grabbing" : "default" }}
      >
        {/* Big emoji "photo" */}
        <Flex
          align="center"
          justify="center"
          h="100%"
          fontSize="140px"
          lineHeight="1"
          filter="drop-shadow(0 8px 16px rgba(0,0,0,0.25))"
        >
          {item.emoji}
        </Flex>

        {/* LIKE / NOPE stamps */}
        <Box
          position="absolute"
          top="28px"
          left="24px"
          px="3"
          py="1"
          border="4px solid"
          borderColor="green.300"
          color="green.300"
          borderRadius="lg"
          fontWeight="extrabold"
          fontSize="2xl"
          letterSpacing="wider"
          transform="rotate(-18deg)"
          opacity={likeOpacity}
          pointerEvents="none"
        >
          LIKE
        </Box>
        <Box
          position="absolute"
          top="28px"
          right="24px"
          px="3"
          py="1"
          border="4px solid"
          borderColor="red.400"
          color="red.400"
          borderRadius="lg"
          fontWeight="extrabold"
          fontSize="2xl"
          letterSpacing="wider"
          transform="rotate(18deg)"
          opacity={nopeOpacity}
          pointerEvents="none"
        >
          NOPE
        </Box>

        {/* Info gradient overlay */}
        <Box
          position="absolute"
          bottom="0"
          left="0"
          right="0"
          p="5"
          pt="16"
          color="white"
          background="linear-gradient(to top, rgba(0,0,0,0.72), rgba(0,0,0,0))"
        >
          <Flex align="baseline" gap="2">
            <Text fontSize="2xl" fontWeight="bold" lineHeight="1.1">
              {item.title}
            </Text>
          </Flex>
          <Text fontSize="sm" opacity={0.85} mt="1">
            {item.owner} · {item.distance}
          </Text>
          <Text fontSize="sm" mt="2" opacity={0.95}>
            {item.description}
          </Text>
          <HStack gap="2" mt="3" flexWrap="wrap">
            {item.tags.map((tag) => (
              <Badge
                key={tag}
                bg="whiteAlpha.300"
                color="white"
                borderRadius="full"
                px="2.5"
                py="0.5"
                fontSize="xs"
              >
                {tag}
              </Badge>
            ))}
          </HStack>
        </Box>
      </Box>
    )
  }
)
