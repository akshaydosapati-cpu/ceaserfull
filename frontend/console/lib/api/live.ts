import { apiRequest } from "./client"

export type LiveProviderState = {
  name: string
  configured: boolean
  status: string
  message?: string | null
}

export type LiveStatus = {
  news: LiveProviderState
  weather: LiveProviderState
  search: LiveProviderState
  market: LiveProviderState
  maps: LiveProviderState
  google_calendar: LiveProviderState
  gmail: LiveProviderState
  google_drive: LiveProviderState
  microsoft: LiveProviderState
  notion: LiveProviderState
  canvas: LiveProviderState
  moodle: LiveProviderState
}

export type LiveArticle = {
  title: string
  source?: string | null
  url?: string | null
  published_at?: string | null
  summary?: string | null
  image_url?: string | null
}

export type LiveNewsBrief = {
  query: string
  mode: string
  provider: string
  configured: boolean
  articles: LiveArticle[]
  error?: string | null
}

export type LiveWeatherReport = {
  location: string
  provider: string
  configured: boolean
  temperature?: number | null
  condition?: string | null
  humidity?: number | null
  wind_speed?: number | null
  error?: string | null
}

export const liveApi = {
  status: () => apiRequest<LiveStatus>("/live/status"),
  latestNews: () => apiRequest<LiveNewsBrief>("/live/news/latest"),
  searchNews: (query: string) => apiRequest<LiveNewsBrief>(`/live/news/search?q=${encodeURIComponent(query)}`),
  categoryNews: (category: string) => apiRequest<LiveNewsBrief>(`/live/news/category/${encodeURIComponent(category)}`),
  currentWeather: (location?: string) => {
    const query = location ? `?location=${encodeURIComponent(location)}` : ""
    return apiRequest<LiveWeatherReport>(`/live/weather/current${query}`)
  },
}
