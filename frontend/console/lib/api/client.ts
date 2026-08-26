type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown
  cacheTtlMs?: number
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  process.env.NEXT_PUBLIC_CEASER_API_URL ??
  "https://ceaser-backend-production.onrender.com"

const ACCESS_TOKEN_KEY = "ceaser_access_token"
const REFRESH_TOKEN_KEY = "ceaser_refresh_token"
let refreshPromise: Promise<string | null> | null = null
const CACHE_PREFIX = "ceaser_api_cache:"
const DEFAULT_CACHE_TTL_MS = 60_000

export function getAccessToken() {
  if (typeof window === "undefined") return null
  return window.localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function getRefreshToken() {
  if (typeof window === "undefined") return null
  return window.localStorage.getItem(REFRESH_TOKEN_KEY)
}

export function setAuthTokens(accessToken?: string | null, refreshToken?: string | null) {
  if (typeof window === "undefined") return
  if (accessToken) {
    window.localStorage.setItem(ACCESS_TOKEN_KEY, accessToken)
  }
  if (refreshToken) {
    window.localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
  }
}

export function clearAuthTokens() {
  if (typeof window === "undefined") return
  window.localStorage.removeItem(ACCESS_TOKEN_KEY)
  window.localStorage.removeItem(REFRESH_TOKEN_KEY)
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message)
    this.name = "ApiError"
  }
}

async function refreshAccessToken() {
  const refreshToken = getRefreshToken()
  if (!refreshToken) return null
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
      signal: AbortSignal.timeout(10000),
    })
      .then(async (response) => {
        if (!response.ok) return null
        const session = await response.json()
        setAuthTokens(session.access_token, session.refresh_token)
        return session.access_token || null
      })
      .catch(() => null)
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

function shouldRefresh(path: string) {
  return !["/auth/login", "/auth/signup", "/auth/refresh", "/auth/password/recover", "/auth/email/resend-verification"].some(
    (authPath) => path.startsWith(authPath),
  )
}

async function request<T>(path: string, options: RequestOptions, accessToken: string | null): Promise<Response> {
  return fetch(`${API_BASE_URL}${path}`, {
    ...options,
    signal: options.signal ?? AbortSignal.timeout(path.startsWith("/auth/") ? 10000 : 8000),
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...options.headers,
    },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  })
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = String(options.method || "GET").toUpperCase()
  const cacheable = method === "GET" && canCache(path)
  const cacheKey = cacheable ? cacheKeyFor(path) : ""
  const ttl = options.cacheTtlMs ?? DEFAULT_CACHE_TTL_MS
  if (cacheable) {
    const cached = readCache<T>(cacheKey, ttl)
    if (cached.fresh) return cached.value as T
  }

  const accessToken = getAccessToken()
  let response: Response
  try {
    response = await request<T>(path, options, accessToken)
  } catch (error) {
    if (cacheable) {
      const cached = readCache<T>(cacheKey, Number.POSITIVE_INFINITY)
      if (cached.exists) return cached.value as T
    }
    throw error
  }

  if (response.status === 401 && shouldRefresh(path)) {
    const refreshedToken = await refreshAccessToken()
    if (refreshedToken) {
      response = await request<T>(path, options, refreshedToken)
    }
  }

  if (!response.ok) {
    let message = `CEASER API request failed: ${path}`
    try {
      const payload = await response.json()
      if (payload?.detail) message = typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail)
    } catch {
      // Keep default message when the API does not return JSON.
    }
    if (response.status === 401) {
      clearAuthTokens()
      if (typeof window !== "undefined" && !path.startsWith("/auth/")) {
        window.dispatchEvent(new CustomEvent("ceaser:session-expired"))
      }
    }
    throw new ApiError(message, response.status)
  }

  if (response.status === 204) {
    return undefined as T
  }

  const payload = (await response.json()) as T
  if (cacheable) writeCache(cacheKey, payload)
  return payload
}

export async function apiStreamRequest(
  path: string,
  options: RequestOptions = {},
  handlers: {
    onStatus?: (payload: Record<string, unknown>) => void
    onToken?: (text: string) => void
    onComplete?: (payload: Record<string, unknown>) => void
    onError?: (message: string) => void
  } = {},
) {
  const accessToken = getAccessToken()
  let response = await request(path, options, accessToken)

  if (response.status === 401 && shouldRefresh(path)) {
    const refreshedToken = await refreshAccessToken()
    if (refreshedToken) response = await request(path, options, refreshedToken)
  }

  if (!response.ok || !response.body) {
    let message = "We couldn't complete your request. Please try again."
    try {
      const payload = await response.json()
      if (payload?.detail) message = typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail)
    } catch {
      // Keep friendly message.
    }
    throw new ApiError(message, response.status)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  const dispatchEvent = (raw: string) => {
    const lines = raw.split("\n")
    const eventName = lines.find((line) => line.startsWith("event:"))?.replace("event:", "").trim()
    const dataLine = lines.find((line) => line.startsWith("data:"))?.replace("data:", "").trim()
    if (!eventName || !dataLine) return
    let payload: Record<string, unknown> | string = dataLine
    try {
      payload = JSON.parse(dataLine) as Record<string, unknown>
    } catch {
      // Some stream events send raw text chunks.
    }
    if (eventName === "status" && typeof payload !== "string") handlers.onStatus?.(payload)
    if (eventName === "token") handlers.onToken?.(typeof payload === "string" ? payload : String(payload.text ?? ""))
    if (eventName === "complete" && typeof payload !== "string") handlers.onComplete?.(payload)
    if (eventName === "error") {
      const message = typeof payload === "string" ? payload : String(payload.message ?? "We couldn't complete your request. Please try again.")
      handlers.onError?.(message)
    }
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const events = buffer.split("\n\n")
    buffer = events.pop() ?? ""
    for (const raw of events) dispatchEvent(raw)
  }
  if (buffer.trim()) dispatchEvent(buffer)
}

function canCache(path: string) {
  if (typeof window === "undefined") return false
  if (path.startsWith("/auth/")) return false
  return [
    "/agents",
    "/agent-workbenches",
    "/automations",
    "/conversations",
    "/documents",
    "/drafts",
    "/files",
    "/memories",
    "/projects",
    "/voice/settings",
    "/workflows",
  ].some((prefix) => path.startsWith(prefix))
}

function cacheKeyFor(path: string) {
  const token = getAccessToken() || "anon"
  return `${CACHE_PREFIX}${token.slice(0, 18)}:${API_BASE_URL}:${path}`
}

function readCache<T>(key: string, ttlMs: number): { exists: boolean; fresh: boolean; value?: T } {
  try {
    const raw = window.localStorage.getItem(key)
    if (!raw) return { exists: false, fresh: false }
    const parsed = JSON.parse(raw) as { savedAt: number; value: T }
    const fresh = Date.now() - parsed.savedAt <= ttlMs
    return { exists: true, fresh, value: parsed.value }
  } catch {
    return { exists: false, fresh: false }
  }
}

function writeCache<T>(key: string, value: T) {
  try {
    window.localStorage.setItem(key, JSON.stringify({ savedAt: Date.now(), value }))
  } catch {
    // Cache is best-effort only.
  }
}
