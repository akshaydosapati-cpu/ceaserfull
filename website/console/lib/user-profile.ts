export type UserProfile = {
  name?: string
  email?: string
  useCase?: string
}

export const PROFILE_KEY = "ceaser_user_profile"

export function readUserProfile(): UserProfile | null {
  if (typeof window === "undefined") return null
  try {
    return JSON.parse(window.localStorage.getItem(PROFILE_KEY) || "null") as UserProfile | null
  } catch {
    return null
  }
}

export function getUserDisplayName(profile?: UserProfile | null, fallback = "CEASER User") {
  return profile?.name?.trim() || fallback
}

export function getUserDisplayRole(profile?: UserProfile | null, fallback = "Founder") {
  return profile?.useCase?.trim() || fallback
}
