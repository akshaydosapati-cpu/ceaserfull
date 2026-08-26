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
  provider_subscription_id?: string | null
  current_period_start?: string | null
  current_period_end?: string | null
  cancel_at_period_end?: boolean
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

export type BillingPayment = {
  id: string
  provider_payment_id: string
  provider_invoice_id?: string | null
  amount: number
  currency: string
  status: string
  method?: string | null
  captured_at?: string | null
  extra_metadata: Record<string, unknown>
}

export type BillingInvoice = {
  id: string
  provider: string
  provider_invoice_id: string
  invoice_number?: string | null
  amount: number
  currency: string
  status: string
  hosted_url?: string | null
  issued_at?: string | null
  due_at?: string | null
  paid_at?: string | null
  extra_metadata: Record<string, unknown>
}

export type BillingSubscriptionOverview = {
  plan: CommercialPlan
  subscription: CommercialSubscription | null
  entitlements: CommercialEntitlement[]
  usage: UsageSummaryItem[]
  payments: BillingPayment[]
  invoices: BillingInvoice[]
  student_pricing_available: boolean
  feature_access?: Record<string, unknown> | null
}

export type BillingCreateOrderResponse = {
  order_id: string
  amount: number
  currency: string
  key_id: string
  receipt: string
  plan_code?: string | null
  billing_interval?: string | null
  name: string
  description?: string | null
  prefill_email?: string | null
  prefill_name?: string | null
  theme_color?: string | null
}

export type BillingCreateSubscriptionResponse = {
  provider: string
  key_id: string
  checkout_mode: string
  subscription_id: string
  customer_id?: string | null
  plan_code: string
  billing_interval: string
  amount?: number | null
  currency: string
  name: string
  description?: string | null
  prefill_email?: string | null
  prefill_name?: string | null
  theme_color?: string | null
}

export type BillingVerifyPaymentResponse = {
  status: string
  message: string
  subscription?: CommercialSubscription | null
}

export type BillingManageResponse = {
  status: string
  message: string
  subscription?: CommercialSubscription | null
}

export const commercialApi = {
  plans: () => apiRequest<CommercialPlan[]>("/commercial/plans", { cacheTtlMs: 30_000 }),
  overview: () => apiRequest<CommercialOverview>("/commercial/me", { cacheTtlMs: 10_000 }),
  billingOverview: () => apiRequest<BillingSubscriptionOverview>("/billing/subscription", { cacheTtlMs: 10_000 }),
  studentStatus: () => apiRequest<StudentVerification | null>("/commercial/student/status", { cacheTtlMs: 10_000 }),
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
  createOrder: (planCode: string, billingInterval: "monthly" | "annual") =>
    apiRequest<BillingCreateOrderResponse>("/billing/create-order", {
      method: "POST",
      body: { amount: 100, currency: "INR", plan_code: planCode, billing_interval: billingInterval },
    }),
  createSubscription: (planCode: string, billingInterval: "monthly" | "annual") =>
    apiRequest<BillingCreateSubscriptionResponse>("/billing/create-subscription", {
      method: "POST",
      body: { plan_code: planCode, billing_interval: billingInterval },
    }),
  verifyPayment: (payload: {
    razorpay_payment_id: string
    razorpay_order_id: string
    razorpay_subscription_id?: string
    razorpay_signature: string
  }) =>
    apiRequest<BillingVerifyPaymentResponse>("/billing/verify-payment", {
      method: "POST",
      body: payload,
    }),
  cancelSubscription: () =>
    apiRequest<BillingManageResponse>("/billing/cancel", {
      method: "POST",
    }),
  resumeSubscription: () =>
    apiRequest<BillingManageResponse>("/billing/resume", {
      method: "POST",
    }),
  invoices: () => apiRequest<BillingInvoice[]>("/billing/invoices", { cacheTtlMs: 10_000 }),
}
