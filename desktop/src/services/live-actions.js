const { getEnv } = require("./env")

async function getWeather(location = "Hyderabad, IN") {
  const apiKey = getEnv("WEATHER_API_KEY")
  if (!apiKey) return { status: "error", message: "Weather is not configured yet." }
  const requested = String(location || "Hyderabad, IN").trim()
  const url = new URL("https://api.openweathermap.org/data/2.5/weather")
  url.searchParams.set("q", requested)
  url.searchParams.set("appid", apiKey)
  url.searchParams.set("units", getEnv("WEATHER_DEFAULT_UNITS", "metric"))
  try {
    const response = await fetch(url)
    const payload = await response.json()
    if (!response.ok) return { status: "error", message: `I could not get weather for ${requested}.` }
    const condition = title(payload.weather?.[0]?.description || "weather")
    const temp = Math.round(Number(payload.main?.temp))
    const humidity = payload.main?.humidity
    const wind = payload.wind?.speed
    const place = [payload.name, payload.sys?.country].filter(Boolean).join(", ")
    return {
      status: "completed",
      message: `${place || requested}: ${temp}°C, ${condition}. Humidity ${humidity ?? "unknown"}%. Wind ${wind ?? "unknown"} m/s.`,
      weather: { location: place || requested, temperature: temp, condition, humidity, wind_speed: wind },
    }
  } catch (_error) {
    return { status: "error", message: "Weather service is unavailable right now." }
  }
}

async function getNews(query = "latest news") {
  const apiKey = getEnv("NEWS_API_KEY")
  if (!apiKey) return { status: "error", message: "News is not configured yet." }
  const cleaned = String(query || "latest news").trim()
  const isLatest = /\b(latest|today|headlines|top news|daily news)\b/i.test(cleaned)
  const topic = newsTopic(cleaned)
  try {
    let payload = await fetchNewsApi(buildNewsUrl({ apiKey, useTopHeadlines: isLatest && !topic, topic: topic || "India technology startup business" }))
    let articles = normalizeArticles(payload)
    if (!articles.length) {
      payload = await fetchNewsApi(buildNewsUrl({ apiKey, useTopHeadlines: false, topic: topic || "technology OR business OR India" }))
      articles = normalizeArticles(payload)
    }
    if (!articles.length) return { status: "error", message: "I could not find useful news results for that." }
    const message = articles.map((article, index) => `${index + 1}. ${article.title} - ${article.source}`).join("\n")
    return { status: "completed", message, articles }
  } catch (_error) {
    return { status: "error", message: "News service is unavailable right now." }
  }
}

function buildNewsUrl({ apiKey, useTopHeadlines, topic }) {
  const url = new URL(useTopHeadlines ? "https://newsapi.org/v2/top-headlines" : "https://newsapi.org/v2/everything")
  if (useTopHeadlines) {
    url.searchParams.set("country", getEnv("NEWS_DEFAULT_REGION", "IN").toLowerCase())
  } else {
    url.searchParams.set("q", topic)
    url.searchParams.set("language", getEnv("NEWS_DEFAULT_LANGUAGE", "en"))
    url.searchParams.set("sortBy", "publishedAt")
  }
  url.searchParams.set("pageSize", "5")
  url.searchParams.set("apiKey", apiKey)
  return url
}

async function fetchNewsApi(url) {
  const response = await fetch(url)
  const payload = await response.json()
  if (!response.ok) throw new Error(payload.message || "I could not get the news right now.")
  return payload
}

function normalizeArticles(payload) {
  return (payload.articles || [])
    .filter((article) => article?.title && article.title !== "[Removed]")
    .slice(0, 5)
    .map((article) => ({
      title: article.title,
      source: article.source?.name || "News source",
      url: article.url,
      summary: article.description || "",
      image_url: article.urlToImage || "",
      published_at: article.publishedAt ? new Date(article.publishedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "Latest",
    }))
}

function newsTopic(value) {
  const cleaned = String(value || "")
    .replace(/\b(latest|today|top|news|headlines|updates|stories|brief|briefing|about|on|for|give me|show me|read)\b/gi, " ")
    .replace(/\s+/g, " ")
    .trim()
  if (/^(ai)$/i.test(cleaned)) return "artificial intelligence"
  return cleaned.length >= 2 ? cleaned : ""
}

function title(value) {
  return String(value || "").replace(/\b\w/g, (letter) => letter.toUpperCase())
}

module.exports = { getNews, getWeather }
