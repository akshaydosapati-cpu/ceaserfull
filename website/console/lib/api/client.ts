type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown
  cacheTtlMs?: number
}

export function getApiBaseUrl() {
  // An explicit environment URL must win, including during local frontend
  // development. This lets localhost use the deployed Render backend instead
  // of silently switching to a stale local backend.
  const configuredUrl = process.env.NEXT_PUBLIC_API_URL ?? process.env.NEXT_PUBLIC_CEASER_API_URL
  if (configuredUrl) return configuredUrl.replace(/\/$/, "")
  if (process.env.NODE_ENV !== "production") {
    return "http://127.0.0.1:8000"
  }
  return "https://ceaser-backend-production-ur04.onrender.com"
}

const API_BASE_URL = getApiBaseUrl()

const ACCESS_TOKEN_KEY = "ceaser_access_token"
const REFRESH_TOKEN_KEY = "ceaser_refresh_token"
let refreshPromise: Promise<string | null> | null = null
const CACHE_PREFIX = "ceaser_api_cache:"
const DEFAULT_CACHE_TTL_MS = 60_000
const inFlightRequests = new Map<string, Promise<unknown>>()

export type StartupMetricName =
  | "app_navigation_start"
  | "shell_visible"
  | "composer_rendered"
  | "input_interactive"
  | "auth_verify_start"
  | "auth_ready"
  | "first_api_start"
  | "first_api_response"
  | "conversation_list_ready"
  | "core_data_ready"
  | "secondary_data_ready"

export function recordStartupMetric(name: StartupMetricName, detail: Record<string, unknown> = {}) {
  if (typeof window === "undefined") return
  const elapsedMs = Math.round(performance.now())
  performance.mark(`ceaser:${name}`)
  window.dispatchEvent(new CustomEvent("ceaser:startup-metric", {
    detail: { name, elapsed_ms: elapsedMs, ...detail },
  }))
  console.info("[CEASER STARTUP]", name, { elapsed_ms: elapsedMs, ...detail })
}

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
  invalidateApiCache()
  inFlightRequests.clear()
}

export function invalidateApiCache(pathPrefixes: string[] = []) {
  if (typeof window === "undefined") return
  try {
    const keysToRemove: string[] = []
    for (let index = 0; index < window.localStorage.length; index += 1) {
      const key = window.localStorage.key(index)
      if (!key || !key.startsWith(CACHE_PREFIX)) continue
      if (!pathPrefixes.length) {
        keysToRemove.push(key)
        continue
      }
      if (pathPrefixes.some((prefix) => key.includes(`:${prefix}`))) {
        keysToRemove.push(key)
      }
    }
    keysToRemove.forEach((key) => window.localStorage.removeItem(key))
  } catch {
    // Cache invalidation is best-effort only.
  }
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

function isSessionAuthError(message: string, path: string) {
  if (path.startsWith("/auth/")) return true
  const normalized = message.trim().toLowerCase()
  return [
    "missing bearer token",
    "invalid session",
    "invalid supabase user",
    "sign in required",
    "session expired",
  ].includes(normalized)
}

async function refreshAccessToken() {
  const refreshToken = getRefreshToken()
  if (!refreshToken) return null
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
      signal: AbortSignal.timeout(20000),
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
  const startedAt = typeof performance === "undefined" ? 0 : performance.now()
  if (typeof window !== "undefined" && !performance.getEntriesByName("ceaser:first_api_start").length) {
    recordStartupMetric("first_api_start", { path })
  }
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      signal: options.signal ?? AbortSignal.timeout(timeoutFor(path)),
      headers: {
        "Content-Type": "application/json",
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        ...options.headers,
      },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    })
    if (typeof window !== "undefined" && !performance.getEntriesByName("ceaser:first_api_response").length) {
      const totalMs = Math.round(performance.now() - startedAt)
      const serverMs = Number(response.headers.get("x-process-time-ms") || 0)
      recordStartupMetric("first_api_response", {
        path,
        total_ms: totalMs,
        server_processing_ms: serverMs || null,
        estimated_network_ms: serverMs ? Math.max(0, totalMs - serverMs) : null,
      })
    }
    return response
  } catch (error) {
    if (error instanceof DOMException && error.name === "TimeoutError") {
      throw new ApiError("CEASER is taking longer than expected. Please try again.", 408)
    }
    throw error
  }
}

function timeoutFor(path: string) {
  if (path.startsWith("/auth/")) return 20000
  if (
    path.startsWith("/commercial") ||
    path.startsWith("/billing") ||
    path.startsWith("/ceaser/chat") ||
    path.startsWith("/chat/") ||
    path.startsWith("/conversations") ||
    path.startsWith("/drafts") ||
    path.startsWith("/documents") ||
    path.startsWith("/knowledge/orchestrate")
  ) {
    return path.startsWith("/commercial") || path.startsWith("/billing") ? 30000 : 180000
  }
  if (/^\/files\/[^/]+\/analyze$/.test(path)) return 90000
  // Render can need a short cold-start window for ordinary data endpoints.
  // Keep generation-specific limits above, but do not fail a page load after
  // only 12 seconds while the service is waking up.
  return 30000
}

async function apiRequestInternal<T>(path: string, options: RequestOptions = {}): Promise<T> {
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
    if (response.status === 401 && isSessionAuthError(message, path)) {
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

export function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = String(options.method || "GET").toUpperCase()
  if (method !== "GET" || !canCache(path)) return apiRequestInternal<T>(path, options)
  const key = cacheKeyFor(path)
  const existing = inFlightRequests.get(key)
  if (existing) return existing as Promise<T>
  const pending = apiRequestInternal<T>(path, options).finally(() => inFlightRequests.delete(key))
  inFlightRequests.set(key, pending)
  return pending
}

export async function apiStreamRequest(
  path: string,
  options: RequestOptions = {},
  handlers: {
    onStatus?: (payload: Record<string, unknown>) => void
    onToken?: (text: string) => void
    onComplete?: (payload: Record<string, unknown>) => void
    onActivity?: (payload: Record<string, unknown>) => void
    onBlock?: (payload: Record<string, unknown>) => void
    onResponseStarted?: (payload: Record<string, unknown>) => void
    onResponseCompleted?: (payload: Record<string, unknown>) => void
    onError?: (message: string) => void
  } = {},
) {
  const accessToken = getAccessToken()
  const streamOptions: RequestOptions = {
    ...options,
    headers: {
      Accept: "text/event-stream",
      "Cache-Control": "no-cache",
      ...options.headers,
    },
  }
  let response = await request(path, streamOptions, accessToken)

  if (response.status === 401 && shouldRefresh(path)) {
    const refreshedToken = await refreshAccessToken()
    if (refreshedToken) response = await request(path, streamOptions, refreshedToken)
  }

  if (!response.ok || !response.body) {
    if (response.status === 429) {
      throw new ApiError("You're sending requests pretty quickly. Try again in a few seconds.", 429)
    }
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
    const dataLine = lines.find((line) => line.startsWith("data:"))?.replace(/^data:\s?/, "")
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
    if (eventName === "activity" && typeof payload !== "string") handlers.onActivity?.(payload)
    if ((eventName === "block.created" || eventName === "block.updated") && typeof payload !== "string") handlers.onBlock?.(payload)
    if (eventName === "response.started" && typeof payload !== "string") handlers.onResponseStarted?.(payload)
    if (eventName === "response.completed" && typeof payload !== "string") handlers.onResponseCompleted?.(payload)
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
  // Chat turns change while an answer is streaming. A cached history can show
  // only the user prompt after refresh and hide the saved assistant response.
  if (/^\/chat\/conversations\/[^/]+\/messages(?:\?|$)/.test(path)) return false
  return [
    "/agents",
    "/agent-workbenches",
    "/automations",
    "/chat/conversations",
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
