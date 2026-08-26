import type { ClientPayload } from './types'

declare global {
  interface Window {
    Razorpay: new (options: RazorpayOptions) => { open: () => void }
  }
}

export interface RazorpayHandlerResponse {
  razorpay_payment_id: string
  razorpay_order_id: string
  razorpay_signature: string
}

export interface RazorpayOptions {
  key: string
  order_id: string
  amount: number
  currency: string
  name?: string
  handler: (response: RazorpayHandlerResponse) => void
  modal?: { ondismiss?: () => void }
}

let loadPromise: Promise<void> | null = null

/** Lazily loads Razorpay's Checkout script — only called once a payment is
 * actually ready to be collected, never at app startup. */
export function loadRazorpayScript(): Promise<void> {
  if (typeof window !== 'undefined' && window.Razorpay) return Promise.resolve()
  if (loadPromise) return loadPromise

  loadPromise = new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = 'https://checkout.razorpay.com/v1/checkout.js'
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('Failed to load Razorpay checkout script'))
    document.body.appendChild(script)
  })
  return loadPromise
}

export async function openCheckout(
  clientPayload: ClientPayload,
  onSuccess: (response: RazorpayHandlerResponse) => void,
  onDismiss: () => void,
): Promise<void> {
  await loadRazorpayScript()
  const rzp = new window.Razorpay({
    key: clientPayload.key_id,
    order_id: clientPayload.order_id,
    amount: clientPayload.amount,
    currency: clientPayload.currency,
    name: 'AP2 Demo Store',
    handler: onSuccess,
    modal: { ondismiss: onDismiss },
  })
  rzp.open()
}
