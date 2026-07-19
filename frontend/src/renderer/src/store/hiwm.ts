import { defineStore } from 'pinia'
import {
  HIWM_TIMELINE_STORAGE_KEY,
  LEGACY_TIMELINE_STORAGE_KEYS,
  readMigratedStorage,
  writeProjectStorage,
} from '../utils/projectStorage.ts'

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

export type HiwmContentSignal = {
  id: string
  category: 'need' | 'concern' | 'commitment' | 'question' | 'unknown'
  statement: string
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
  information_gain?: number
  evidence_refs: string[]
}

export type HiwmPlannerWeights = {
  goal: number
  risk: number
  uncertainty: number
  information_gain?: number
}

export type HiwmActionScore = {
  action_id: string
  score: number
  goal_component: number
  risk_component: number
  uncertainty_component: number
  information_gain_component?: number
}

export type HiwmPlanner = {
  formula: 'goal-risk-uncertainty-v1' | 'goal-information-gain-risk-uncertainty-v2'
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
  content_signals: HiwmContentSignal[]
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

export type HiwmTimelineEventType =
  | 'content_evidence_observed'
  | 'visual_evidence_observed'
  | 'prosody_evidence_observed'
  | 'prediction_generated'
  | 'locked'
  | 'robot_response'
  | 'actual_response'
  | 'evaluated'
  | 'profile_updated'

export type HiwmDerivedMeasurement = string | number | boolean | null

export type HiwmEvidenceObservedPayload = {
  modality: 'content' | 'visual' | 'prosody'
  kind: 'final_transcript' | 'face_features' | 'speech_features'
  label: string
  source_evidence_id: string
  stream_key: string | null
  value: number | null
  unit: string | null
  quality: number | null
  measurements: Readonly<Record<string, HiwmDerivedMeasurement>>
  raw_media_included: false
}

export type HiwmPredictionGeneratedPayload = {
  objective: string
  content_signals: readonly HiwmContentSignal[]
  actions: readonly HiwmAction[]
  selected_action_id: string
  planner?: Readonly<HiwmPlanner>
  model_name: string
  probability_kind: HiwmModel['probability_kind']
}

export type HiwmLockedPayload = {
  prediction_id: string
  action_id: string
  sha256: string
}

export type HiwmRobotResponsePayload = {
  action_id: string
  strategy: string
  utterance: string
}

export type HiwmActualResponsePayload = {
  previous_turn_id: string
  content: string
  evidence_refs: readonly string[]
}

export type HiwmEvaluatedPayload = {
  previous_turn_id: string
  comparison: HiwmFeedback['comparison']
  explanation: string
}

export type HiwmProfileUpdatedPayload = {
  beliefs: readonly HiwmBelief[]
}

export type HiwmTimelinePayload =
  | HiwmEvidenceObservedPayload
  | HiwmPredictionGeneratedPayload
  | HiwmLockedPayload
  | HiwmRobotResponsePayload
  | HiwmActualResponsePayload
  | HiwmEvaluatedPayload
  | HiwmProfileUpdatedPayload

/**
 * A derived, append-only audit event. It intentionally contains no raw image,
 * video, audio, PCM, or binary payloads.
 */
export type HiwmTimelineEvent = {
  readonly event_id: string
  readonly session_id: string
  readonly turn_id: string
  readonly type: HiwmTimelineEventType
  readonly occurred_at: number
  readonly recorded_at: number
  readonly source_snapshot_sha256: string
  readonly payload: Readonly<HiwmTimelinePayload>
}

export type HiwmTimelineExport = {
  readonly schema_version: '1.0'
  readonly exported_at: number
  readonly session_id: string
  readonly raw_media_included: false
  readonly events: readonly HiwmTimelineEvent[]
}

interface HiwmTurnState {
  schemaVersion: '1.0' | null
  turnId: string
  objective: string
  observation: HiwmObservation | null
  contentSignals: HiwmContentSignal[]
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
  sessionTimelines: Record<string, readonly HiwmTimelineEvent[]>
}

const TIMELINE_STORAGE_VERSION = '1.0'
const MAX_TIMELINE_EVENTS = 200

const emptyTurnState = (): HiwmTurnState => ({
  schemaVersion: null,
  turnId: '',
  objective: '',
  observation: null,
  contentSignals: [],
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

const emptyState = (): HiwmState => {
  const restored = loadTimelineStorage()
  return {
    activeSessionId: restored.lastActiveSessionId,
    sessionTimelines: restored.sessions,
    ...emptyTurnState(),
  }
}

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

const isContentSignal = (value: unknown): value is HiwmContentSignal => {
  if (!isRecord(value)) return false
  if (
    !hasContractKeys(value, [
      'id',
      'category',
      'statement',
      'confidence',
      'evidence_refs',
      'change',
    ])
  ) {
    return false
  }
  return (
    isNonBlankString(value.id) &&
    (value.category === 'need' ||
      value.category === 'concern' ||
      value.category === 'commitment' ||
      value.category === 'question' ||
      value.category === 'unknown') &&
    isNonBlankString(value.statement) &&
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
    !hasContractKeys(
      value,
      [
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
      ],
      ['information_gain']
    )
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
    (value.information_gain === undefined || isProbability(value.information_gain)) &&
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
  if (
    !isRecord(value) ||
    !hasContractKeys(value, ['goal', 'risk', 'uncertainty'], ['information_gain'])
  ) {
    return false
  }
  return (
    isNonNegativeNumber(value.goal) &&
    isNonNegativeNumber(value.risk) &&
    isNonNegativeNumber(value.uncertainty) &&
    (value.information_gain === undefined || isNonNegativeNumber(value.information_gain)) &&
    (value.goal > 0 ||
      value.risk > 0 ||
      value.uncertainty > 0 ||
      (isFiniteNumber(value.information_gain) && value.information_gain > 0))
  )
}

const isActionScore = (value: unknown): value is HiwmActionScore =>
  isRecord(value) &&
  hasContractKeys(
    value,
    ['action_id', 'score', 'goal_component', 'risk_component', 'uncertainty_component'],
    ['information_gain_component']
  ) &&
  isNonBlankString(value.action_id) &&
  isFiniteNumber(value.score) &&
  isFiniteNumber(value.goal_component) &&
  isFiniteNumber(value.risk_component) &&
  isFiniteNumber(value.uncertainty_component) &&
  (value.information_gain_component === undefined ||
    isFiniteNumber(value.information_gain_component))

const isPlanner = (value: unknown): value is HiwmPlanner => {
  if (!isRecord(value)) return false
  if (!hasContractKeys(value, ['formula', 'weights', 'scores', 'selected_action_id'])) return false
  const hasValidFormula =
    value.formula === 'goal-risk-uncertainty-v1' ||
    value.formula === 'goal-information-gain-risk-uncertainty-v2'
  if (
    !hasValidFormula ||
    !isPlannerWeights(value.weights) ||
    !Array.isArray(value.scores) ||
    value.scores.length !== 3 ||
    !value.scores.every(isActionScore) ||
    !isNonBlankString(value.selected_action_id)
  ) {
    return false
  }
  if (value.formula === 'goal-information-gain-risk-uncertainty-v2') {
    return (
      isFiniteNumber(value.weights.information_gain) &&
      value.weights.information_gain > 0 &&
      value.scores.every(
        (score) => isRecord(score) && isFiniteNumber(score.information_gain_component)
      )
    )
  }
  return true
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
      'content_signals',
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
    !Array.isArray(value.content_signals) ||
    value.content_signals.length < 1 ||
    value.content_signals.length > 20 ||
    !value.content_signals.every(isContentSignal) ||
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

  const contentSignalIds = value.content_signals.map((item) => item.id)
  const beliefIds = value.beliefs.map((item) => item.id)
  const actionIds = value.actions.map((item) => item.action_id)
  const actionStrategies = value.actions.map((item) => item.strategy.toLocaleLowerCase())
  const actionUtterances = value.actions.map((item) => item.utterance.toLocaleLowerCase())
  const scoreActionIds = value.planner.scores.map((score) => score.action_id)
  if (
    !hasUniqueValues(contentSignalIds) ||
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
    value.content_signals.every(
      (signal) => refsAreKnown(signal.evidence_refs) && signal.evidence_refs.includes(currentAsrId)
    ) &&
    value.beliefs.every((belief) => refsAreKnown(belief.evidence_refs)) &&
    value.actions.every(
      (action) => refsAreKnown(action.evidence_refs) && action.evidence_refs.includes(currentAsrId)
    ) &&
    (value.feedback === null ||
      (refsAreKnown(value.feedback.evidence_refs) &&
        value.feedback.evidence_refs.includes(currentAsrId)))
  )
}

const timelineEventTypes = new Set<HiwmTimelineEventType>([
  'content_evidence_observed',
  'visual_evidence_observed',
  'prosody_evidence_observed',
  'prediction_generated',
  'locked',
  'robot_response',
  'actual_response',
  'evaluated',
  'profile_updated',
])

const forbiddenRawMediaFieldNames = new Set([
  'audio',
  'audiodata',
  'rawaudio',
  'video',
  'videodata',
  'rawvideo',
  'image',
  'imagedata',
  'frame',
  'frames',
  'pcm',
  'wav',
  'blob',
  'base64',
  'binary',
  'bytes',
  'rawmedia',
])

const containsRawMediaField = (value: unknown): boolean => {
  if (Array.isArray(value)) return value.some(containsRawMediaField)
  if (!isRecord(value)) return false
  return Object.entries(value).some(([key, nestedValue]) => {
    const normalizedKey = key.replace(/[-_]/g, '').toLowerCase()
    return forbiddenRawMediaFieldNames.has(normalizedKey) || containsRawMediaField(nestedValue)
  })
}

const isTimelineEventType = (value: unknown): value is HiwmTimelineEventType =>
  typeof value === 'string' && timelineEventTypes.has(value as HiwmTimelineEventType)

const isPredictionGeneratedPayload = (value: unknown): value is HiwmPredictionGeneratedPayload =>
  isRecord(value) &&
  hasContractKeys(
    value,
    [
      'objective',
      'content_signals',
      'actions',
      'selected_action_id',
      'model_name',
      'probability_kind',
    ],
    ['planner']
  ) &&
  isNonBlankString(value.objective) &&
  Array.isArray(value.content_signals) &&
  value.content_signals.length >= 1 &&
  value.content_signals.length <= 20 &&
  value.content_signals.every(isContentSignal) &&
  Array.isArray(value.actions) &&
  value.actions.length === 3 &&
  value.actions.every(isAction) &&
  isNonBlankString(value.selected_action_id) &&
  value.actions.some((action) => action.action_id === value.selected_action_id) &&
  (value.planner === undefined ||
    (isPlanner(value.planner) && value.planner.selected_action_id === value.selected_action_id)) &&
  isNonBlankString(value.model_name) &&
  value.probability_kind === 'uncalibrated_model_estimate'

const isLockedPayload = (value: unknown): value is HiwmLockedPayload =>
  isRecord(value) &&
  hasContractKeys(value, ['prediction_id', 'action_id', 'sha256']) &&
  isNonBlankString(value.prediction_id) &&
  isNonBlankString(value.action_id) &&
  isSha256(value.sha256)

const isRobotResponsePayload = (value: unknown): value is HiwmRobotResponsePayload =>
  isRecord(value) &&
  hasContractKeys(value, ['action_id', 'strategy', 'utterance']) &&
  isNonBlankString(value.action_id) &&
  isNonBlankString(value.strategy) &&
  isNonBlankString(value.utterance)

const isActualResponsePayload = (value: unknown): value is HiwmActualResponsePayload =>
  isRecord(value) &&
  hasContractKeys(value, ['previous_turn_id', 'content', 'evidence_refs']) &&
  isNonBlankString(value.previous_turn_id) &&
  isNonBlankString(value.content) &&
  isEvidenceReferenceList(value.evidence_refs)

const isEvaluatedPayload = (value: unknown): value is HiwmEvaluatedPayload =>
  isRecord(value) &&
  hasContractKeys(value, ['previous_turn_id', 'comparison', 'explanation']) &&
  isNonBlankString(value.previous_turn_id) &&
  (value.comparison === 'matched' ||
    value.comparison === 'partial' ||
    value.comparison === 'miss' ||
    value.comparison === 'indeterminate') &&
  isNonBlankString(value.explanation)

const isProfileUpdatedPayload = (value: unknown): value is HiwmProfileUpdatedPayload =>
  isRecord(value) &&
  hasContractKeys(value, ['beliefs']) &&
  Array.isArray(value.beliefs) &&
  value.beliefs.length > 0 &&
  value.beliefs.every(isBelief)

const isDerivedMeasurement = (value: unknown): value is HiwmDerivedMeasurement =>
  value === null ||
  (typeof value === 'string' &&
    value.length <= 512 &&
    !/^data:(?:image|audio|video)\//i.test(value.trim())) ||
  typeof value === 'boolean' ||
  isFiniteNumber(value)

const isEvidenceObservedPayload = (value: unknown): value is HiwmEvidenceObservedPayload => {
  if (
    !isRecord(value) ||
    !hasContractKeys(value, [
      'modality',
      'kind',
      'label',
      'source_evidence_id',
      'stream_key',
      'value',
      'unit',
      'quality',
      'measurements',
      'raw_media_included',
    ]) ||
    (value.modality !== 'content' && value.modality !== 'visual' && value.modality !== 'prosody') ||
    (value.kind !== 'final_transcript' &&
      value.kind !== 'face_features' &&
      value.kind !== 'speech_features') ||
    !isNonBlankString(value.label) ||
    !isNonBlankString(value.source_evidence_id) ||
    (value.stream_key !== null && typeof value.stream_key !== 'string') ||
    (value.value !== null && !isFiniteNumber(value.value)) ||
    (value.unit !== null && typeof value.unit !== 'string') ||
    (value.quality !== null && !isProbability(value.quality)) ||
    !isRecord(value.measurements) ||
    Object.keys(value.measurements).length === 0 ||
    Object.keys(value.measurements).length > 20 ||
    !Object.values(value.measurements).every(isDerivedMeasurement) ||
    value.raw_media_included !== false
  ) {
    return false
  }
  return (
    (value.modality === 'content' && value.kind === 'final_transcript') ||
    (value.modality === 'visual' && value.kind === 'face_features') ||
    (value.modality === 'prosody' && value.kind === 'speech_features')
  )
}

const isTimelinePayload = (
  type: HiwmTimelineEventType,
  value: unknown
): value is HiwmTimelinePayload => {
  if (containsRawMediaField(value)) return false
  switch (type) {
    case 'content_evidence_observed':
      return isEvidenceObservedPayload(value) && value.modality === 'content'
    case 'visual_evidence_observed':
      return isEvidenceObservedPayload(value) && value.modality === 'visual'
    case 'prosody_evidence_observed':
      return isEvidenceObservedPayload(value) && value.modality === 'prosody'
    case 'prediction_generated':
      return isPredictionGeneratedPayload(value)
    case 'locked':
      return isLockedPayload(value)
    case 'robot_response':
      return isRobotResponsePayload(value)
    case 'actual_response':
      return isActualResponsePayload(value)
    case 'evaluated':
      return isEvaluatedPayload(value)
    case 'profile_updated':
      return isProfileUpdatedPayload(value)
  }
}

const isTimelineEvent = (value: unknown): value is HiwmTimelineEvent => {
  if (!isRecord(value)) return false
  if (
    !hasContractKeys(value, [
      'event_id',
      'session_id',
      'turn_id',
      'type',
      'occurred_at',
      'recorded_at',
      'source_snapshot_sha256',
      'payload',
    ]) ||
    !isNonBlankString(value.event_id) ||
    !isNonBlankString(value.session_id) ||
    !isNonBlankString(value.turn_id) ||
    !isTimelineEventType(value.type) ||
    !isNonNegativeNumber(value.occurred_at) ||
    !isNonNegativeNumber(value.recorded_at) ||
    !isSha256(value.source_snapshot_sha256)
  ) {
    return false
  }
  return isTimelinePayload(value.type, value.payload)
}

const deepFreeze = <T>(value: T): T => {
  if (value && typeof value === 'object' && !Object.isFrozen(value)) {
    Object.values(value as Record<string, unknown>).forEach(deepFreeze)
    Object.freeze(value)
  }
  return value
}

const cloneAction = (action: HiwmAction): HiwmAction => ({
  ...action,
  predicted_state_delta: action.predicted_state_delta.map((delta) => ({ ...delta })),
  evidence_refs: [...action.evidence_refs],
})

const cloneBelief = (belief: HiwmBelief): HiwmBelief => ({
  ...belief,
  evidence_refs: [...belief.evidence_refs],
})

const cloneContentSignal = (signal: HiwmContentSignal): HiwmContentSignal => ({
  ...signal,
  evidence_refs: [...signal.evidence_refs],
})

const clonePlanner = (planner: HiwmPlanner): HiwmPlanner => ({
  ...planner,
  weights: { ...planner.weights },
  scores: planner.scores.map((score) => ({ ...score })),
})

const immutableTimelineEvent = (event: HiwmTimelineEvent): HiwmTimelineEvent =>
  deepFreeze({
    ...event,
    payload: { ...event.payload },
  } as HiwmTimelineEvent)

type TimelineStorageEnvelope = {
  schema_version: '1.0'
  saved_at: number
  last_active_session_id: string | null
  sessions: Record<string, readonly HiwmTimelineEvent[]>
}

function loadTimelineStorage(): {
  lastActiveSessionId: string
  sessions: Record<string, readonly HiwmTimelineEvent[]>
} {
  if (typeof window === 'undefined' || !window.localStorage) {
    return { lastActiveSessionId: '', sessions: {} }
  }
  try {
    const serialized = readMigratedStorage(HIWM_TIMELINE_STORAGE_KEY, LEGACY_TIMELINE_STORAGE_KEYS)
    if (!serialized) return { lastActiveSessionId: '', sessions: {} }
    const parsed: unknown = JSON.parse(serialized)
    if (
      !isRecord(parsed) ||
      parsed.schema_version !== TIMELINE_STORAGE_VERSION ||
      !isRecord(parsed.sessions)
    ) {
      return { lastActiveSessionId: '', sessions: {} }
    }

    const sessions: Record<string, readonly HiwmTimelineEvent[]> = {}
    Object.entries(parsed.sessions).forEach(([sessionId, candidateEvents]) => {
      if (!isNonBlankString(sessionId) || !Array.isArray(candidateEvents)) return
      const seen = new Set<string>()
      const validEvents = candidateEvents
        .reduce<HiwmTimelineEvent[]>((events, event) => {
          if (
            !isTimelineEvent(event) ||
            event.session_id !== sessionId ||
            seen.has(event.event_id)
          ) {
            return events
          }
          seen.add(event.event_id)
          events.push(immutableTimelineEvent(event))
          return events
        }, [])
        .slice(-MAX_TIMELINE_EVENTS)
      sessions[sessionId] = validEvents
    })

    const lastActiveSessionId =
      typeof parsed.last_active_session_id === 'string' &&
      Object.prototype.hasOwnProperty.call(sessions, parsed.last_active_session_id)
        ? parsed.last_active_session_id
        : ''
    return { lastActiveSessionId, sessions }
  } catch (error) {
    console.warn('Unable to restore HIWM timeline', error)
    return { lastActiveSessionId: '', sessions: {} }
  }
}

export const buildTimelineEvents = (snapshot: HiwmSnapshot): HiwmTimelineEvent[] => {
  const recordedAt = Date.now() / 1000
  const sourceHash = snapshot.locked_prediction.sha256
  const createEvent = (
    type: HiwmTimelineEventType,
    occurredAt: number,
    payload: HiwmTimelinePayload
  ): HiwmTimelineEvent =>
    immutableTimelineEvent({
      event_id: `${snapshot.session_id}:${snapshot.turn_id}:${type}`,
      session_id: snapshot.session_id,
      turn_id: snapshot.turn_id,
      type,
      occurred_at: occurredAt,
      recorded_at: recordedAt,
      source_snapshot_sha256: sourceHash,
      payload,
    })

  const events: HiwmTimelineEvent[] = []
  const currentAsr = snapshot.observation.current_asr
  events.push(
    createEvent('content_evidence_observed', currentAsr.observed_at, {
      modality: 'content',
      kind: 'final_transcript',
      label: currentAsr.content || '已确认的用户字幕',
      source_evidence_id: currentAsr.evidence_id,
      stream_key: currentAsr.stream_key || null,
      value: null,
      unit: null,
      quality: 1,
      measurements: {
        finalized: true,
        source: currentAsr.source,
      },
      raw_media_included: false,
    })
  )

  const perception = isRecord(currentAsr.metadata.perception)
    ? currentAsr.metadata.perception
    : null
  const perceptionObservedAt =
    perception && isNonNegativeNumber(perception.observed_at)
      ? perception.observed_at
      : currentAsr.observed_at
  const face = perception && isRecord(perception.face) ? perception.face : null
  if (face) {
    const facePresent = face.face_present === true
    const yaw = isFiniteNumber(face.yaw) ? face.yaw : null
    const pitch = isFiniteNumber(face.pitch) ? face.pitch : null
    const trackingQuality = isProbability(face.tracking_quality) ? face.tracking_quality : null
    const observableFeatures = Array.isArray(face.observable_features)
      ? face.observable_features
          .filter((item): item is string => typeof item === 'string')
          .slice(0, 16)
          .join(', ')
      : ''
    const pose = [
      yaw === null ? '' : `yaw ${yaw.toFixed(1)}°`,
      pitch === null ? '' : `pitch ${pitch.toFixed(1)}°`,
    ]
      .filter(Boolean)
      .join(' · ')
    events.push(
      createEvent('visual_evidence_observed', perceptionObservedAt, {
        modality: 'visual',
        kind: 'face_features',
        label: facePresent ? `面部跟踪已建立${pose ? ` · ${pose}` : ''}` : '当前未跟踪到面部',
        source_evidence_id: currentAsr.evidence_id,
        stream_key: currentAsr.stream_key || null,
        value: trackingQuality,
        unit: trackingQuality === null ? null : 'ratio',
        quality: trackingQuality,
        measurements: {
          face_present: facePresent,
          yaw,
          pitch,
          tracking_quality: trackingQuality,
          observable_features: observableFeatures || null,
        },
        raw_media_included: false,
      })
    )
  } else if (snapshot.observation.camera) {
    events.push(
      createEvent('visual_evidence_observed', snapshot.observation.camera.observed_at, {
        modality: 'visual',
        kind: 'face_features',
        label: '摄像头证据已采集，当前没有可回放的派生面部特征',
        source_evidence_id: snapshot.observation.camera.evidence_id,
        stream_key: snapshot.observation.camera.stream_key || null,
        value: null,
        unit: null,
        quality: null,
        measurements: {
          derived_face_features_available: false,
        },
        raw_media_included: false,
      })
    )
  }

  const speech = perception && isRecord(perception.speech) ? perception.speech : null
  if (speech) {
    const speechActive = speech.speech_active === true
    const rms = isProbability(speech.rms) ? speech.rms : null
    const pitchHz = isFiniteNumber(speech.pitch_hz) ? speech.pitch_hz : null
    const pitchDelta = isFiniteNumber(speech.pitch_delta) ? speech.pitch_delta : null
    const energyDelta = isFiniteNumber(speech.energy_delta) ? speech.energy_delta : null
    const pauseMs = isNonNegativeNumber(speech.pause_ms) ? speech.pause_ms : null
    const speechRate = isNonNegativeNumber(speech.speech_rate) ? speech.speech_rate : null
    const summary = [
      pitchHz === null ? '' : `音高 ${pitchHz.toFixed(1)} Hz`,
      rms === null ? '' : `能量 ${Math.round(rms * 100)}%`,
      pauseMs === null ? '' : `停顿 ${Math.round(pauseMs)} ms`,
      speechRate === null ? '' : `语速 ${speechRate.toFixed(2)} 词/秒`,
    ]
      .filter(Boolean)
      .join(' · ')
    events.push(
      createEvent('prosody_evidence_observed', perceptionObservedAt, {
        modality: 'prosody',
        kind: 'speech_features',
        label: summary || (speechActive ? '检测到用户正在说话' : '当前为静音窗口'),
        source_evidence_id: currentAsr.evidence_id,
        stream_key: currentAsr.stream_key || null,
        value: rms,
        unit: rms === null ? null : 'ratio',
        quality: null,
        measurements: {
          speech_active: speechActive,
          rms,
          pitch_hz: pitchHz,
          pitch_delta_hz: pitchDelta,
          energy_delta_ratio: energyDelta,
          pause_ms: pauseMs,
          speech_rate_per_second: speechRate,
        },
        raw_media_included: false,
      })
    )
  }

  if (snapshot.feedback) {
    events.push(
      createEvent('actual_response', snapshot.observation.current_asr.observed_at, {
        previous_turn_id: snapshot.feedback.previous_turn_id,
        content: snapshot.feedback.actual_observation,
        evidence_refs: [...snapshot.feedback.evidence_refs],
      }),
      createEvent('evaluated', snapshot.model.completed_at, {
        previous_turn_id: snapshot.feedback.previous_turn_id,
        comparison: snapshot.feedback.comparison,
        explanation: snapshot.feedback.explanation,
      })
    )
  }

  const changedBeliefs = snapshot.beliefs
    .filter((belief) => belief.change !== 'unchanged')
    .map(cloneBelief)
  if (changedBeliefs.length) {
    events.push(
      createEvent('profile_updated', snapshot.model.completed_at, {
        beliefs: changedBeliefs,
      })
    )
  }

  const selectedAction = snapshot.actions.find(
    (action) => action.action_id === snapshot.selected_action_id
  )!
  events.push(
    createEvent('prediction_generated', snapshot.model.completed_at, {
      objective: snapshot.objective,
      content_signals: snapshot.content_signals.map(cloneContentSignal),
      actions: snapshot.actions.map(cloneAction),
      selected_action_id: snapshot.selected_action_id,
      planner: clonePlanner(snapshot.planner),
      model_name: snapshot.model.model_name,
      probability_kind: snapshot.model.probability_kind,
    }),
    createEvent('locked', snapshot.locked_at, {
      prediction_id: snapshot.locked_prediction.prediction_id,
      action_id: snapshot.locked_prediction.action_id,
      sha256: snapshot.locked_prediction.sha256,
    }),
    createEvent('robot_response', snapshot.locked_at, {
      action_id: selectedAction.action_id,
      strategy: selectedAction.strategy,
      utterance: selectedAction.utterance,
    })
  )
  return events
}

export const useHiwmStore = defineStore('hiwmStore', {
  state: (): HiwmState => emptyState(),
  getters: {
    timeline(state): readonly HiwmTimelineEvent[] {
      if (!state.activeSessionId) return []
      return state.sessionTimelines[state.activeSessionId] || []
    },
    timelineSessionIds(state): string[] {
      return Object.keys(state.sessionTimelines)
    },
  },
  actions: {
    beginSession(sessionId: string): void {
      this.switchSession(sessionId)
    },

    switchSession(sessionId: string): void {
      if (!isNonBlankString(sessionId)) return
      this.activeSessionId = sessionId
      this.clearTurnSnapshot()
      if (!Object.prototype.hasOwnProperty.call(this.sessionTimelines, sessionId)) {
        this.sessionTimelines = {
          ...this.sessionTimelines,
          [sessionId]: [],
        }
      }
      this.persistTimelineStorage()
    },

    clearSession(): void {
      this.activeSessionId = ''
      this.clearTurnSnapshot()
      this.persistTimelineStorage()
    },

    clearTurnSnapshot(): void {
      Object.assign(this, emptyTurnState())
    },

    persistTimelineStorage(): void {
      if (typeof window === 'undefined' || !window.localStorage) return
      const envelope: TimelineStorageEnvelope = {
        schema_version: TIMELINE_STORAGE_VERSION,
        saved_at: Date.now() / 1000,
        last_active_session_id: this.activeSessionId || null,
        sessions: this.sessionTimelines,
      }
      try {
        writeProjectStorage(
          HIWM_TIMELINE_STORAGE_KEY,
          JSON.stringify(envelope),
          LEGACY_TIMELINE_STORAGE_KEYS
        )
      } catch (error) {
        console.warn('Unable to persist HIWM timeline', error)
      }
    },

    appendTimelineEvents(sessionId: string, events: readonly HiwmTimelineEvent[]): void {
      if (!isNonBlankString(sessionId) || !events.length) return
      const existing = this.sessionTimelines[sessionId] || []
      const seenIds = new Set(existing.map((event) => event.event_id))
      const additions = events.reduce<HiwmTimelineEvent[]>((deduped, event) => {
        if (
          event.session_id !== sessionId ||
          !isTimelineEvent(event) ||
          seenIds.has(event.event_id)
        ) {
          return deduped
        }
        seenIds.add(event.event_id)
        deduped.push(immutableTimelineEvent(event))
        return deduped
      }, [])
      if (!additions.length) return

      // Replace the array instead of mutating prior events. A repeated snapshot
      // can append a missing stage, but can never recompute or overwrite history.
      this.sessionTimelines = {
        ...this.sessionTimelines,
        [sessionId]: [...existing, ...additions].slice(-MAX_TIMELINE_EVENTS),
      }
      this.persistTimelineStorage()
    },

    deleteSession(sessionId?: string): boolean {
      const targetSessionId = sessionId ?? this.activeSessionId
      if (
        !targetSessionId ||
        !Object.prototype.hasOwnProperty.call(this.sessionTimelines, targetSessionId)
      ) {
        return false
      }
      const { [targetSessionId]: _removed, ...remaining } = this.sessionTimelines
      void _removed
      this.sessionTimelines = remaining
      if (this.activeSessionId === targetSessionId) {
        const remainingSessionIds = Object.keys(remaining)
        // Object key order follows the session insertion order. Prefer the most
        // recently inserted surviving session so replay stays immediately usable.
        this.activeSessionId = remainingSessionIds[remainingSessionIds.length - 1] || ''
        this.clearTurnSnapshot()
      }
      this.persistTimelineStorage()
      return true
    },

    exportSession(sessionId?: string): string | null {
      const targetSessionId = sessionId ?? this.activeSessionId
      const events = this.sessionTimelines[targetSessionId]
      if (!targetSessionId || !events) return null
      const exported: HiwmTimelineExport = {
        schema_version: '1.0',
        exported_at: Date.now() / 1000,
        session_id: targetSessionId,
        raw_media_included: false,
        events,
      }
      return JSON.stringify(exported, null, 2)
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
      this.contentSignals = snapshot.content_signals
      this.beliefs = snapshot.beliefs
      this.actions = snapshot.actions
      this.selectedActionId = snapshot.selected_action_id
      this.planner = snapshot.planner
      this.lockedAt = snapshot.locked_at
      this.lockedPrediction = snapshot.locked_prediction
      this.feedback = snapshot.feedback
      this.model = snapshot.model
      this.error = ''
      this.appendTimelineEvents(snapshot.session_id, buildTimelineEvents(snapshot))
    },
  },
})
