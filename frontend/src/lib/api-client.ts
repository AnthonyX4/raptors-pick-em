// every request goes through here: it adds the token, turns fastapi's error shapes into one ApiError,
// and survives an expired token on public pages. urls are always relative (/api/...), the dev proxy
// and nginx forward them, so there is no api base url and no cors

const TOKEN_KEY = "raptors_token"

// localStorage can throw (private windows, blocked storage), and the app must still load
export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token: string) {
  try {
    localStorage.setItem(TOKEN_KEY, token)
  } catch {
    // no storage: the session lasts until the page is closed
  }
}

export function clearToken() {
  try {
    localStorage.removeItem(TOKEN_KEY)
  } catch {
    // nothing to clear
  }
}

// the AuthProvider (16.2) registers here so a 401 also resets the user held in react state
let onAuthReset: (() => void) | null = null
export function setAuthResetHandler(handler: (() => void) | null) {
  onAuthReset = handler
}

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

type Query = Record<string, string | number | boolean | null | undefined>

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE"
  query?: Query
  json?: unknown // sent as application/json
  form?: Record<string, string> // sent form-encoded: only the login uses this
  multipart?: FormData // the avatar upload; the browser sets the boundary, so no content-type here
  signal?: AbortSignal
}

function buildUrl(path: string, query?: Query) {
  if (!query) return path
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null) params.set(key, String(value))
  }
  const text = params.toString()
  return text ? `${path}?${text}` : path
}

// fastapi sends {"detail": "message"}, or for a 422 {"detail": [{loc, msg, ...}]}
async function errorFrom(response: Response): Promise<ApiError> {
  let message = response.statusText || "Something went wrong"
  try {
    const body = await response.json()
    if (typeof body?.detail === "string") {
      message = body.detail
    } else if (Array.isArray(body?.detail)) {
      message = body.detail
        .map((item: { msg?: string }) => (item.msg ?? "").replace(/^Value error, /, ""))
        .filter(Boolean)
        .join(". ")
    }
  } catch {
    // not json (a proxy error page, say): keep the status text
  }
  return new ApiError(response.status, message)
}

async function send(path: string, options: RequestOptions, token: string | null): Promise<Response> {
  const headers: Record<string, string> = {}
  if (token) headers.Authorization = `Bearer ${token}`

  let body: BodyInit | undefined
  if (options.json !== undefined) {
    headers["Content-Type"] = "application/json"
    body = JSON.stringify(options.json)
  } else if (options.form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    body = new URLSearchParams(options.form)
  } else if (options.multipart) {
    body = options.multipart
  }

  try {
    return await fetch(buildUrl(path, options.query), {
      method: options.method ?? "GET",
      headers,
      body,
      signal: options.signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error
    throw new ApiError(0, "Can't reach the server. Check your connection and try again.")
  }
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const token = getToken()
  let response = await send(path, options, token)

  // public endpoints that show more to a logged-in reader still 401 a stale token instead of treating
  // the reader as anonymous, so drop the token and ask once more without it
  if (response.status === 401 && token) {
    clearToken()
    onAuthReset?.()
    response = await send(path, options, null)
  }

  if (!response.ok) throw await errorFrom(response)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

type BodylessOptions = Omit<RequestOptions, "method" | "json" | "form" | "multipart">

export const api = {
  get: <T>(path: string, options?: BodylessOptions) => request<T>(path, options),
  post: <T>(path: string, json?: unknown) => request<T>(path, { method: "POST", json }),
  put: <T>(path: string, json?: unknown) => request<T>(path, { method: "PUT", json }),
  patch: <T>(path: string, json?: unknown) => request<T>(path, { method: "PATCH", json }),
  delete: <T = void>(path: string) => request<T>(path, { method: "DELETE" }),
  login: <T>(email: string, password: string) =>
    request<T>("/api/users/token", { method: "POST", form: { username: email, password } }),
  upload: <T>(path: string, multipart: FormData) => request<T>(path, { method: "PATCH", multipart }),
}
