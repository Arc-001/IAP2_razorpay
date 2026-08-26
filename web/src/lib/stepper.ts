import type { AgentState } from './types'

export type StageStatus = 'pending' | 'active' | 'done' | 'error'

export interface StepperStage {
  index: number
  label: string
}

export const STAGES: StepperStage[] = [
  { index: 0, label: 'Intent' },
  { index: 1, label: 'Cart' },
  { index: 2, label: 'Payment' },
  { index: 3, label: 'Outcome' },
]

const STAGE_FOR_STATE: Record<AgentState, number> = {
  DRAFTING_INTENT: 0,
  AWAITING_INTENT_OK: 0,
  BUILDING_CART: 1,
  AWAITING_CART_OK: 1,
  EXECUTING_PAYMENT: 2,
  PAYMENT_FAILED: 2,
  TERMINAL: 3,
}

/** Which of the 4 stages is active/done/error for a given orchestrator state, null before the first turn. */
export function activeStageIndex(state: AgentState | null): number | null {
  if (state === null) return null
  return STAGE_FOR_STATE[state]
}

export function stageStatus(stageIndex: number, state: AgentState | null): StageStatus {
  const active = activeStageIndex(state)
  if (active === null) return 'pending'
  if (stageIndex < active) return 'done'
  if (stageIndex > active) return 'pending'
  // stageIndex === active
  if (state === 'PAYMENT_FAILED') return 'error'
  if (state === 'TERMINAL') return 'done'
  return 'active'
}
