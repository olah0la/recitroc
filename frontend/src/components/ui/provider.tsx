import { ChakraProvider, defaultSystem } from "@chakra-ui/react"
import type { PropsWithChildren } from "react"

export function Provider(props: PropsWithChildren) {
  return <ChakraProvider value={defaultSystem}>{props.children}</ChakraProvider>
}
