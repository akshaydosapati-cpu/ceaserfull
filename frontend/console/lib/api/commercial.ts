import { apiRequest } from "./client"

export type CommercialPlan = {
  id: string
  code: string
  name: string
  description: string
  currency: string
  monthly_price: number
  annual_price: number
  active: boolean
  public: boolean
}

export type CommercialEntitlement = {
  id: string
  entitlement_key: string
  limit_value: number
  value_type: string
  reset_period: string
}

export type UsageSummaryItem = {
  entitlement_key: string
  limit_value: number
  used_quantity: number
  remaining: number
  reset_period: string
}

export type CommercialSubscription = {
  id: string
  provider: string
  status: string
  billing_interval: string
  current_period_start?: string | null
  current_period_end?: string | null
}

export type StudentVerification = {
  id: string
  institutional_email?: string | null
  verification_method?: string | null
  status: string
  document_file_id?: string | null
  verified_at?: string | null
  expires_at?: string | null
  rejection_reason?: string | null
}

export type CommercialOverview = {
  plan: CommercialPlan
  subscription: CommercialSubscription | null
  student_verification: StudentVerification | null
  entitlements: CommercialEntitlement[]
  usage: UsageSummaryItem[]
  student_pricing_available: boolean
}

export const commercialApi = {
  plans: () => apiRequest<CommercialPlan[]>("/commercial/plans", { cacheTtlMs: 30_000 }),
  overview: () => apiRequest<CommercialOverview>("/commercial/me", { cacheTtlMs: 10_000 }),
  startStudentEmail: (institutionalEmail: string) =>
    apiRequest<{ status: string; message: string; verification_id?: string | null }>("/commercial/student/email/start", {
      method: "POST",
      body: { institutional_email: institutionalEmail },
    }),
  confirmStudentEmail: (verificationId: string, otp: string) =>
    apiRequest<StudentVerification>("/commercial/student/email/confirm", {
      method: "POST",
      body: { verification_id: verificationId, otp },
    }),
  submitStudentDocument: (documentFileId: string, institutionCode = "NHCE") =>
    apiRequest<StudentVerification>("/commercial/student/document", {
      method: "POST",
      body: { document_file_id: documentFileId, institution_code: institutionCode },
    }),
  testCheckout: (planCode: string, billingInterval: "monthly" | "annual") =>
    apiRequest<{ provider: string; checkout_id: string; status: string; message: string }>("/commercial/checkout/test", {
      method: "POST",
      body: { plan_code: planCode, billing_interval: billingInterval },
    }),
}
