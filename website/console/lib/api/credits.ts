import { apiRequest, invalidateApiCache } from "./client"

export type CreditOverview = {
  plan: string; monthly: number; bonus: number; purchased: number; reserved: number
  total_available: number; monthly_allowance: number; renewal_date: string
  referral: { code: string; link: string; successful: number; pending: number; credits_earned: number }
  history: { id: string; amount: number; balance_type: string; type: string; source: string; created_at: string }[]
}
export type CreditProduct = { id: string; code: string; name: string; credits: number; amount_inr: number }
export type CreditOrder = { purchase_id: string; order_id: string; amount: number; currency: string; credits: number; name: string; key_id: string }

export const creditsApi = {
  overview: () => apiRequest<CreditOverview>("/credits/overview", { cacheTtlMs: 5_000 }),
  products: () => apiRequest<CreditProduct[]>("/credits/products", { cacheTtlMs: 30_000 }),
  applyReferral: (code: string) => apiRequest<{ status: string }>("/credits/referrals/apply", { method: "POST", body: { code } }),
  createOrder: (productId: string) => apiRequest<CreditOrder>("/credits/purchases/order", { method: "POST", body: { product_id: productId } }),
  verify: async (orderId: string, paymentId: string, signature: string) => {
    const result = await apiRequest<{ status: string; credits: number }>("/credits/purchases/verify", { method: "POST", body: { order_id: orderId, payment_id: paymentId, signature } })
    invalidateApiCache(["/credits"])
    return result
  },
}
