import { useState } from "react"
import { MotionBox } from "./motion"
import { Box, Image, Text } from "@chakra-ui/react"

type SwipeCardProps = {
  image: string
  name: string
  onSwipeLeft?: () => void
  onSwipeRight?: () => void
}

export function SwipeCard({
  image,
  name,
  onSwipeLeft,
  onSwipeRight,
}: SwipeCardProps) {
  const [exitX, setExitX] = useState(0)

  return (
    <MotionBox
      position="absolute"
      w="320px"
      h="420px"
      borderRadius="2xl"
      overflow="hidden"
      bg="gray.100"
      drag="x"
      dragConstraints={{ left: 0, right: 0 }}
      whileTap={{ scale: 1.05 }}
      style={{ x: exitX }}
      animate={{ x: exitX }}
      onDragEnd={(_, info) => {
        if (info.offset.x > 120) {
          setExitX(500)
          onSwipeRight?.()
        } else if (info.offset.x < -120) {
          setExitX(-500)
          onSwipeLeft?.()
        } else {
          setExitX(0)
        }
      }}
      transformTemplate={({ rotate }) => `rotate(${rotate})`}
      _active={{ cursor: "grabbing" }}
      cursor="grab"
      boxShadow="xl"
    >
      <Image src={image} objectFit="cover" w="100%" h="100%" />
      <Box position="absolute" bottom="0" p="4" color="white">
        <Text fontSize="2xl" fontWeight="bold">
          {name}
        </Text>
      </Box>
    </MotionBox>
  )
}