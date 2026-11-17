import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { ApiError, api, getToken, request, setAuthResetHandler, setToken } from "@/lib/api-client"

// node has fetch but no localStorage: a map stands in for it, and fetch is replaced per test
function stubStorage() {
  const store = new Map<string, string>()
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => void store.set(key, value),
    removeItem: (key: string) => void store.delete(key),
  })
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } })

// the Authorization header of the n-th fetch call
const authOf = (fetchMock: ReturnType<typeof vi.fn>, call: number) =>
  (fetchMock.mock.calls[call][1].headers as Record<string, string>).Authorization

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  stubStorage()
  fetchMock = vi.fn()
  vi.stubGlobal("fetch", fetchMock)
})

afterEach(() => {
  setAuthResetHandler(null)
  vi.unstubAllGlobals()
})

describe("the token", () => {
  it("goes out as a bearer header", async () => {
    setToken("abc")
    fetchMock.mockResolvedValue(json({ ok: true }))
    await request("/api/users/me")
    expect(authOf(fetchMock, 0)).toBe("Bearer abc")
  })

  it("is left off when there isn't one", async () => {
    fetchMock.mockResolvedValue(json({}))
    await request("/api/games")
    expect(authOf(fetchMock, 0)).toBeUndefined()
  })
})

describe("a 401", () => {
  it("clears the token, tells the auth provider and retries once without the token", async () => {
    setToken("stale")
    const reset = vi.fn()
    setAuthResetHandler(reset)
    fetchMock.mockResolvedValueOnce(json({ detail: "Could not validate credentials" }, 401))
    fetchMock.mockResolvedValueOnce(json({ games: [] }))

    await expect(request("/api/games/1/messages")).resolves.toEqual({ games: [] })

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(authOf(fetchMock, 0)).toBe("Bearer stale")
    expect(authOf(fetchMock, 1)).toBeUndefined()
    expect(getToken()).toBeNull()
    expect(reset).toHaveBeenCalledOnce()
  })

  it("is a plain error when there was no token to blame", async () => {
    const reset = vi.fn()
    setAuthResetHandler(reset)
    fetchMock.mockResolvedValue(json({ detail: "Incorrect email or password" }, 401))

    await expect(api.login("a@b.co", "wrong")).rejects.toMatchObject({ status: 401, message: "Incorrect email or password" })

    expect(fetchMock).toHaveBeenCalledOnce() // no retry
    expect(reset).not.toHaveBeenCalled()
  })

  it("is an error when the retry fails too, and only retries once", async () => {
    setToken("stale")
    fetchMock.mockResolvedValue(json({ detail: "Not authenticated" }, 401))

    await expect(request("/api/users/me")).rejects.toMatchObject({ status: 401 })

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(getToken()).toBeNull()
  })
})

describe("errors", () => {
  it("take the message from a string detail", async () => {
    fetchMock.mockResolvedValue(json({ detail: "Username already exists" }, 409))
    await expect(request("/api/users")).rejects.toThrow(new ApiError(409, "Username already exists"))
  })

  it("join a 422's messages and drop pydantic's prefix", async () => {
    fetchMock.mockResolvedValue(
      json({ detail: [{ msg: "Value error, bad one" }, { msg: "String should have at least 8 characters" }] }, 422),
    )
    await expect(request("/api/users")).rejects.toMatchObject({
      status: 422,
      message: "bad one. String should have at least 8 characters",
    })
  })

  it("survive a body that isn't json", async () => {
    fetchMock.mockResolvedValue(new Response("<html>bad gateway</html>", { status: 502, statusText: "Bad Gateway" }))
    await expect(request("/api/games")).rejects.toMatchObject({ status: 502, message: "Bad Gateway" })
  })

  it("become status 0 when the server can't be reached", async () => {
    fetchMock.mockRejectedValue(new TypeError("fetch failed"))
    await expect(request("/api/games")).rejects.toMatchObject({ status: 0 })
  })
})

describe("request bodies", () => {
  it("send the login form-encoded with the email as username", async () => {
    fetchMock.mockResolvedValue(json({ access_token: "t", token_type: "bearer" }))
    await api.login("me@example.com", "password1")

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe("/api/users/token")
    expect(init.method).toBe("POST")
    expect(init.headers["Content-Type"]).toBe("application/x-www-form-urlencoded")
    expect(String(init.body)).toBe("username=me%40example.com&password=password1")
  })

  it("send json with a content type", async () => {
    fetchMock.mockResolvedValue(json({}))
    await api.post("/api/picks", { game_id: "1" })
    const init = fetchMock.mock.calls[0][1]
    expect(init.headers["Content-Type"]).toBe("application/json")
    expect(init.body).toBe('{"game_id":"1"}')
  })

  it("leave undefined and null query values out of the url", async () => {
    fetchMock.mockResolvedValue(json({}))
    await api.get("/api/games", { query: { season: "2026-27", status: undefined, opponent: null, limit: 100 } })
    expect(fetchMock.mock.calls[0][0]).toBe("/api/games?season=2026-27&limit=100")
  })

  it("return undefined for a 204", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }))
    await expect(api.delete("/api/messages/1")).resolves.toBeUndefined()
  })
})
