import { QueryClient } from "@tanstack/react-query"
import { ApiError } from "@/lib/api-client"

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      // a 403/404/409 won't change by asking again; only network trouble and 5xx are worth a retry
      retry: (failureCount, error) => {
        if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false
        return failureCount < 2
      },
    },
  },
})
