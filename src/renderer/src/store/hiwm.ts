import { defineStore } from 'pinia'

export type HiwmEvidenceReference = {
  evidence_id: string
  modality: 'asr' | 'camera' | 'history'
  source: string
  observed_at: number
  stream_key?: string | null
  content?: string | null
  sha256: string
  metadata: Record<string, unknown>
}

export type HiwmObservation = {
  cutoff_at: number
  current_asr: HiwmEvidenceReference
  camera?: HiwmEvidenceReference | null
  history: HiwmEvidenceReference[]
}

export type HiwmBelief = {
  id: string
  statement: string
  status: 'known' | 'working_hypothesis' | 'unknown'
  confidence: number
  evidence_refs: string[]
  change: 'new' | 'updated' | 'unchanged' | 'retracted'
}

export type HiwmStateDelta = {
  target: string
  predicted_change: string
}

export type HiwmAction = {
  action_id: string
  strategy: string
  utterance: string
  predicted_observation: string
  predicted_state_delta: HiwmStateDelta[]
  goal_probability: number
  risk_probability: number
  risk: string
  uncertainty: number
  evidence_refs: string[]
}

export type HiwmPlannerWeights = {
  goal: number
  risk: number
  uncertainty: number
}

export type HiwmActionScore = {
  action_id: string
  score: number
  goal_component: number
  risk_component: number
  uncertainty_component: number
}

export type HiwmPlanner = {
  formula: 'goal-risk-uncertainty-v1'
  weights: HiwmPlannerWeights
  scores: HiwmActionScore[]
  selected_action_id: string
}

export type HiwmLockedPrediction = {
  algorithm: 'sha256'
  prediction_id: string
  action_id: string
  sha256: string
  locked_at: number
}

export type HiwmFeedback = {
  previous_turn_id: string
  actual_observation: string
  comparison: 'matched' | 'partial' | 'miss' | 'indeterminate'
  explanation: string
  evidence_refs: string[]
}

export type HiwmModel = {
  provider: 'openai_compatible'
  model_name: string
  api_url: string
  response_id?: string | null
  requested_at: number
  completed_at: number
  probability_kind: 'uncalibrated_model_estimate'
}

export type HiwmSnapshot = {
  schema_version: '1.0'
  session_id: string
  turn_id: string
  objective: string
  observation: HiwmObservation
  beliefs: HiwmBelief[]
  actions: HiwmAction[]
  selected_action_id: string
  planner: HiwmPlanner
  feedback: HiwmFeedback | null
  model: HiwmModel
  locked_at: number
  locked_prediction: HiwmLockedPrediction
}

export type HiwmBackendError = {
  schema_version: '1.0'
  session_id: string
  turn_id: string
  stage: 'input_validation' | 'api' | 'response_validation' | 'planner' | 'ledger' | 'output'
  code: string
  message: string
  occurred_at: number
}

interface HiwmTurnState {
  schemaVersion: '1.0' | null
  turnId: string
  objective: string
  observation: HiwmObservation | null
  beliefs: HiwmBelief[]
  actions: HiwmAction[]
  selectedActionId: string
  planner: HiwmPlanner | null
  lockedAt: number | null
  lockedPrediction: HiwmLockedPrediction | null
  feedback: HiwmFeedback | null
  model: HiwmModel | null
  error: string
}

interface HiwmState extends HiwmTurnState {
  activeSessionId: string
}

const emptyTurnState = (): HiwmTurnState => ({
  schemaVersion: null,
  turnId: '',
  objective: '',
  observation: null,
  beliefs: [],
  actions: [],
  selectedActionId: '',
  planner: null,
  lockedAt: null,
  lockedPrediction: null,
  feedback: null,
  model: null,
  error: '',
})

const emptyState = (): HiwmState => ({
  activeSessionId: '',
  ...emptyTurnState(),
})

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const hasOwn = (value: Record<string, unknown>, key: string): boolean =>
  Object.prototype.hasOwnProperty.call(value, key)

const hasContractKeys = (
  value: Record<string, unknown>,
  required: readonly string[],
  optional: readonly string[] = []
): boolean => {
  const allowed = new Set([...required, ...optional])
  return (
    required.every((key) => hasOwn(value, key)) &&
    Object.keys(value).every((key) => allowed.has(key))
  )
}

const isNonBlankString = (value: unknown): value is string =>
  typeof value === 'string' && value.trim().length > 0

const isFiniteNumber = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value)

const isNonNegativeNumber = (value: unknown): value is number => isFiniteNumber(value) && value >= 0

const isProbability = (value: unknown): value is number =>
  isFiniteNumber(value) && value >= 0 && value <= 1

const isNullableString = (value: unknown): value is string | null | undefined =>
  value === undefined || value === null || typeof value === 'string'

const hasUniqueValues = (values: readonly string[]): boolean =>
  new Set(values).size === values.length

const isEvidenceReferenceList = (value: unknown): value is string[] =>
  Array.isArray(value) &&
  value.length > 0 &&
  value.every(isNonBlankString) &&
  hasUniqueValues(value)

const isSha256 = (value: unknown): value is string =>
  typeof value === 'string' && /^[0-9a-f]{64}$/.test(value)

const isEvidenceReference = (
  value: unknown,
  expectedModality?: HiwmEvidenceReference['modality']
): value is HiwmEvidenceReference => {
  if (!isRecord(value)) return false
  if (
    !hasContractKeys(
      value,
      ['evidence_id', 'modality', 'source', 'observed_at', 'sha256', 'metadata'],
      ['stream_key', 'content']
    )
  ) {
    return false
  }
  const modality = value.modality
  return (
    isNonBlankString(value.evidence_id) &&
    (modality === 'asr' || modality === 'camera' || modality === 'history') &&
    (expectedModality === undefined || modality === expectedModality) &&
    isNonBlankString(value.source) &&
    isNonNegativeNumber(value.observed_at) &&
    isNullableString(value.stream_key) &&
    isNullableString(value.content) &&
    isSha256(value.sha256) &&
    isRecord(value.metadata)
  )
}

const isObservation = (value: unknown): value is HiwmObservation => {
  if (!isRecord(value)) return false
  if (!hasContractKeys(value, ['cutoff_at', 'current_asr', 'history'], ['camera'])) return false
  if (
    !isNonNegativeNumber(value.cutoff_at) ||
    !isEvidenceReference(value.current_asr, 'asr') ||
    !isNonBlankString(value.current_asr.content) ||
    (value.camera !== undefined &&
      value.camera !== null &&
      !isEvidenceReference(value.camera, 'camera')) ||
    !Array.isArray(value.history) ||
    !value.history.every(
      (item) => isEvidenceReference(item, 'history') && isNonBlankString(item.content)
    )
  ) {
    return false
  }

  const evidenceIds = [
    value.current_asr.evidence_id,
    ...(isRecord(value.camera) ? [value.camera.evidence_id as string] : []),
    ...value.history.map((item) => item.evidence_id as string),
  ]
  return hasUniqueValues(evidenceIds)
}

const isBelief = (value: unknown): value is HiwmBelief => {
  if (!isRecord(value)) return false
  if (
    !hasContractKeys(value, ['id', 'statement', 'status', 'confidence', 'evidence_refs', 'change'])
  ) {
    return false
  }
  return (
    isNonBlankString(value.id) &&
    isNonBlankString(value.statement) &&
    (value.status === 'known' ||
      value.status === 'working_hypothesis' ||
      value.status === 'unknown') &&
    isProbability(value.confidence) &&
    isEvidenceReferenceList(value.evidence_refs) &&
    (value.change === 'new' ||
      value.change === 'updated' ||
      value.change === 'unchanged' ||
      value.change === 'retracted')
  )
}

const isStateDelta = (value: unknown): value is HiwmStateDelta =>
  isRecord(value) &&
  hasContractKeys(value, ['target', 'predicted_change']) &&
  isNonBlankString(value.target) &&
  isNonBlankString(value.predicted_change)

const isAction = (value: unknown): value is HiwmAction => {
  if (!isRecord(value)) return false
  if (
    !hasContractKeys(value, [
      'action_id',
      'strategy',
      'utterance',
      'predicted_observation',
      'predicted_state_delta',
      'goal_probability',
      'risk_probability',
      'risk',
      'uncertainty',
      'evidence_refs',
    ])
  ) {
    return false
  }
  return (
    isNonBlankString(value.action_id) &&
    isNonBlankString(value.strategy) &&
    isNonBlankString(value.utterance) &&
    isNonBlankString(value.predicted_observation) &&
    Array.isArray(value.predicted_state_delta) &&
    value.predicted_state_delta.length > 0 &&
    value.predicted_state_delta.every(isStateDelta) &&
    isProbability(value.goal_probability) &&
    isProbability(value.risk_probability) &&
    isNonBlankString(value.risk) &&
    isProbability(value.uncertainty) &&
    isEvidenceReferenceList(value.evidence_refs)
  )
}

const isFeedback = (value: unknown): value is HiwmFeedback => {
  if (!isRecord(value)) return false
  if (
    !hasContractKeys(value, [
      'previous_turn_id',
      'actual_observation',
      'comparison',
      'explanation',
      'evidence_refs',
    ])
  ) {
    return false
  }
  return (
    isNonBlankString(value.previous_turn_id) &&
    isNonBlankString(value.actual_observation) &&
    (value.comparison === 'matched' ||
      value.comparison === 'partial' ||
      value.comparison === 'miss' ||
      value.comparison === 'indeterminate') &&
    isNonBlankString(value.explanation) &&
    isEvidenceReferenceList(value.evidence_refs)
  )
}

const isPlannerWeights = (value: unknown): value is HiwmPlannerWeights => {
  if (!isRecord(value) || !hasContractKeys(value, ['goal', 'risk', 'uncertainty'])) return false
  return (
    isNonNegativeNumber(value.goal) &&
    isNonNegativeNumber(value.risk) &&
    isNonNegativeNumber(value.uncertainty) &&
    (value.goal > 0 || value.risk > 0 || value.uncertainty > 0)
  )
}

const isActionScore = (value: unknown): value is HiwmActionScore =>
  isRecord(value) &&
  hasContractKeys(value, [
    'action_id',
    'score',
    'goal_component',
    'risk_component',
    'uncertainty_component',
  ]) &&
  isNonBlankString(value.action_id) &&
  isFiniteNumber(value.score) &&
  isFiniteNumber(value.goal_component) &&
  isFiniteNumber(value.risk_component) &&
  isFiniteNumber(value.uncertainty_component)

const isPlanner = (value: unknown): value is HiwmPlanner => {
  if (!isRecord(value)) return false
  if (!hasContractKeys(value, ['formula', 'weights', 'scores', 'selected_action_id'])) return false
  return (
    value.formula === 'goal-risk-uncertainty-v1' &&
    isPlannerWeights(value.weights) &&
    Array.isArray(value.scores) &&
    value.scores.length === 3 &&
    value.scores.every(isActionScore) &&
    isNonBlankString(value.selected_action_id)
  )
}

const isModel = (value: unknown): value is HiwmModel => {
  if (!isRecord(value)) return false
  if (
    !hasContractKeys(
      value,
      ['provider', 'model_name', 'api_url', 'requested_at', 'completed_at', 'probability_kind'],
      ['response_id']
    )
  ) {
    return false
  }
  return (
    value.provider === 'openai_compatible' &&
    isNonBlankString(value.model_name) &&
    isNonBlankString(value.api_url) &&
    isNullableString(value.response_id) &&
    isNonNegativeNumber(value.requested_at) &&
    isNonNegativeNumber(value.completed_at) &&
    value.completed_at >= value.requested_at &&
    value.probability_kind === 'uncalibrated_model_estimate'
  )
}

const isLockedPrediction = (value: unknown): value is HiwmLockedPrediction => {
  if (!isRecord(value)) return false
  if (!hasContractKeys(value, ['algorithm', 'prediction_id', 'action_id', 'sha256', 'locked_at'])) {
    return false
  }
  return (
    value.algorithm === 'sha256' &&
    isNonBlankString(value.prediction_id) &&
    isNonBlankString(value.action_id) &&
    isSha256(value.sha256) &&
    isNonNegativeNumber(value.locked_at)
  )
}

const isBackendError = (value: unknown): value is HiwmBackendError => {
  if (!isRecord(value)) return false
  if (
    !hasContractKeys(value, [
      'schema_version',
      'session_id',
      'turn_id',
      'stage',
      'code',
      'message',
      'occurred_at',
    ])
  ) {
    return false
  }
  return (
    value.schema_version === '1.0' &&
    isNonBlankString(value.session_id) &&
    isNonBlankString(value.turn_id) &&
    (value.stage === 'input_validation' ||
      value.stage === 'api' ||
      value.stage === 'response_validation' ||
      value.stage === 'planner' ||
      value.stage === 'ledger' ||
      value.stage === 'output') &&
    isNonBlankString(value.code) &&
    isNonBlankString(value.message) &&
    isNonNegativeNumber(value.occurred_at)
  )
}

const isSnapshot = (value: unknown): value is HiwmSnapshot => {
  if (!isRecord(value)) return false
  if (
    !hasContractKeys(value, [
      'schema_version',
      'session_id',
      'turn_id',
      'objective',
      'observation',
      'beliefs',
      'actions',
      'selected_action_id',
      'planner',
      'feedback',
      'model',
      'locked_at',
      'locked_prediction',
    ])
  ) {
    return false
  }
  if (
    value.schema_version !== '1.0' ||
    !isNonBlankString(value.session_id) ||
    !isNonBlankString(value.turn_id) ||
    !isNonBlankString(value.objective) ||
    !isObservation(value.observation) ||
    !Array.isArray(value.beliefs) ||
    value.beliefs.length < 1 ||
    value.beliefs.length > 24 ||
    !value.beliefs.every(isBelief) ||
    !Array.isArray(value.actions) ||
    value.actions.length !== 3 ||
    !value.actions.every(isAction) ||
    !isNonBlankString(value.selected_action_id) ||
    !isPlanner(value.planner) ||
    (value.feedback !== null && !isFeedback(value.feedback)) ||
    !isModel(value.model) ||
    !isNonNegativeNumber(value.locked_at) ||
    !isLockedPrediction(value.locked_prediction)
  ) {
    return false
  }

  const beliefIds = value.beliefs.map((item) => item.id)
  const actionIds = value.actions.map((item) => item.action_id)
  const actionStrategies = value.actions.map((item) => item.strategy.toLocaleLowerCase())
  const actionUtterances = value.actions.map((item) => item.utterance.toLocaleLowerCase())
  const scoreActionIds = value.planner.scores.map((score) => score.action_id)
  if (
    !hasUniqueValues(beliefIds) ||
    !hasUniqueValues(actionIds) ||
    !hasUniqueValues(actionStrategies) ||
    !hasUniqueValues(actionUtterances) ||
    !hasUniqueValues(scoreActionIds) ||
    !actionIds.includes(value.selected_action_id) ||
    value.planner.selected_action_id !== value.selected_action_id ||
    !actionIds.every((actionId) => scoreActionIds.includes(actionId)) ||
    value.locked_prediction.prediction_id !== value.turn_id ||
    value.locked_prediction.action_id !== value.selected_action_id ||
    value.locked_prediction.locked_at !== value.locked_at
  ) {
    return false
  }

  const evidenceIds = new Set([
    value.observation.current_asr.evidence_id,
    ...(value.observation.camera ? [value.observation.camera.evidence_id] : []),
    ...value.observation.history.map((item) => item.evidence_id),
  ])
  const refsAreKnown = (refs: readonly string[]): boolean =>
    refs.every((ref) => evidenceIds.has(ref))
  const currentAsrId = value.observation.current_asr.evidence_id
  return (
    value.beliefs.every((belief) => refsAreKnown(belief.evidence_refs)) &&
    value.actions.every(
      (action) => refsAreKnown(action.evidence_refs) && action.evidence_refs.includes(currentAsrId)
    ) &&
    (value.feedback === null ||
      (refsAreKnown(value.feedback.evidence_refs) &&
        value.feedback.evidence_refs.includes(currentAsrId)))
  )
}

export const useHiwmStore = defineStore('hiwmStore', {
  state: (): HiwmState => emptyState(),
  actions: {
    beginSession(sessionId: string): void {
      this.$reset()
      this.activeSessionId = sessionId
    },

    clearSession(): void {
      this.$reset()
    },

    clearTurnSnapshot(): void {
      Object.assign(this, emptyTurnState())
    },

    consumeAvatarMetadata(metadata: unknown): void {
      if (!this.activeSessionId || !isRecord(metadata)) return

      if (hasOwn(metadata, 'hiwm_error') && metadata.hiwm_error !== null) {
        const backendError = metadata.hiwm_error
        if (
          isRecord(backendError) &&
          typeof backendError.session_id === 'string' &&
          backendError.session_id !== this.activeSessionId
        ) {
          return
        }

        this.clearTurnSnapshot()
        if (isBackendError(backendError)) {
          this.schemaVersion = backendError.schema_version
          this.turnId = backendError.turn_id
          this.error = backendError.message
        } else {
          this.error = 'HIWM 后端错误元数据格式无效'
        }
        return
      }

      if (!hasOwn(metadata, 'hiwm') || metadata.hiwm === null) return
      const snapshot = metadata.hiwm
      if (
        isRecord(snapshot) &&
        typeof snapshot.session_id === 'string' &&
        snapshot.session_id !== this.activeSessionId
      ) {
        return
      }
      if (!isSnapshot(snapshot)) {
        this.clearTurnSnapshot()
        this.error = 'HIWM 后端快照格式无效'
        return
      }

      this.schemaVersion = snapshot.schema_version
      this.turnId = snapshot.turn_id
      this.objective = snapshot.objective
      this.observation = snapshot.observation
      this.beliefs = snapshot.beliefs
      this.actions = snapshot.actions
      this.selectedActionId = snapshot.selected_action_id
      this.planner = snapshot.planner
      this.lockedAt = snapshot.locked_at
      this.lockedPrediction = snapshot.locked_prediction
      this.feedback = snapshot.feedback
      this.model = snapshot.model
      this.error = ''
    },
  },
})
