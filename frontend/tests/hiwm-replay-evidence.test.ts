import assert from 'node:assert/strict'
import { test } from 'node:test'

import { createPinia, setActivePinia } from 'pinia'

import {
  buildTimelineEvents,
  type HiwmSnapshot,
  type HiwmTimelineEvent,
  useHiwmStore,
} from '../src/renderer/src/store/hiwm.ts'

const HASH = 'a'.repeat(64)

function snapshot(): HiwmSnapshot {
  const evidenceId = 'asr:turn-1'
  const actions = ['clarify', 'explain', 'summarize'].map((strategy, index) => ({
    action_id: `action-${index + 1}`,
    strategy,
    utterance: `回应 ${index + 1}`,
    predicted_observation: `预测 ${index + 1}`,
    predicted_state_delta: [{ target: 'shared_context', predicted_change: `变化 ${index + 1}` }],
    goal_probability: 0.7 - index * 0.1,
    risk_probability: 0.1 + index * 0.1,
    risk: `风险 ${index + 1}`,
    uncertainty: 0.2,
    information_gain: 0.3 + index * 0.1,
    evidence_refs: [evidenceId],
  }))
  return {
    schema_version: '1.0',
    session_id: 'session-replay',
    turn_id: 'turn-1',
    objective: '验证可核验回放',
    observation: {
      cutoff_at: 103,
      current_asr: {
        evidence_id: evidenceId,
        modality: 'asr',
        source: 'human_text',
        observed_at: 100,
        stream_key: 'stream-1',
        content: '我需要先确认交付时间。',
        sha256: HASH,
        metadata: {
          finalized: true,
          perception: {
            observed_at: 99.5,
            face: {
              face_present: true,
              yaw: 3.5,
              pitch: -1.2,
              tracking_quality: 0.91,
              observable_features: ['browInnerUp'],
            },
            speech: {
              speech_active: false,
              rms: 0.12,
              pitch_hz: 180,
              pitch_delta: 12,
              energy_delta: 0.2,
              pause_ms: 900,
              speech_rate: 2.1,
            },
          },
        },
      },
      history: [],
    },
    content_signals: [
      {
        id: 'content-1',
        category: 'need',
        statement: '需要确认交付时间',
        confidence: 0.9,
        evidence_refs: [evidenceId],
        change: 'new',
      },
    ],
    beliefs: [
      {
        id: 'belief-1',
        statement: '交付时间仍待确认',
        status: 'unknown',
        confidence: 0.8,
        evidence_refs: [evidenceId],
        change: 'new',
      },
    ],
    actions,
    selected_action_id: 'action-1',
    planner: {
      formula: 'goal-information-gain-risk-uncertainty-v2',
      weights: { goal: 1, risk: 1, uncertainty: 0.5, information_gain: 0.35 },
      scores: actions.map((action) => ({
        action_id: action.action_id,
        score:
          action.goal_probability -
          action.risk_probability -
          action.uncertainty * 0.5 +
          action.information_gain * 0.35,
        goal_component: action.goal_probability,
        risk_component: action.risk_probability,
        uncertainty_component: action.uncertainty * 0.5,
        information_gain_component: action.information_gain * 0.35,
      })),
      selected_action_id: 'action-1',
    },
    feedback: null,
    model: {
      provider: 'openai_compatible',
      model_name: 'offline-test-model',
      api_url: 'https://example.invalid/v1',
      response_id: 'response-1',
      requested_at: 101,
      completed_at: 102,
      probability_kind: 'uncalibrated_model_estimate',
    },
    locked_at: 103,
    locked_prediction: {
      algorithm: 'sha256',
      prediction_id: 'turn-1',
      action_id: 'action-1',
      sha256: HASH,
      locked_at: 103,
    },
  }
}

test('timeline freezes content, visual and prosody evidence without raw media', () => {
  const events = buildTimelineEvents(snapshot())

  assert.deepEqual(
    events.slice(0, 3).map((event) => event.type),
    ['content_evidence_observed', 'visual_evidence_observed', 'prosody_evidence_observed']
  )
  assert.equal(events.length, 7)
  for (const event of events.slice(0, 3)) {
    assert.equal(event.source_snapshot_sha256, HASH)
    assert.equal('raw_media_included' in event.payload, true)
    assert.equal((event.payload as { raw_media_included: boolean }).raw_media_included, false)
  }

  const visual = events[1].payload as { measurements: Record<string, unknown> }
  assert.equal(visual.measurements.tracking_quality, 0.91)
  const prosody = events[2].payload as { measurements: Record<string, unknown> }
  assert.equal(prosody.measurements.pitch_hz, 180)
  assert.equal(prosody.measurements.pause_ms, 900)
  const prediction = events.find((event) => event.type === 'prediction_generated')
  assert.equal(
    (prediction?.payload as { planner?: { formula: string } }).planner?.formula,
    'goal-information-gain-risk-uncertainty-v2'
  )
})

test('a valid v2 backend snapshot appends the complete derived replay sequence', () => {
  setActivePinia(createPinia())
  const store = useHiwmStore()
  store.beginSession('session-replay')

  store.consumeAvatarMetadata({ hiwm: snapshot() })

  assert.equal(store.error, '')
  assert.equal(store.planner?.formula, 'goal-information-gain-risk-uncertainty-v2')
  assert.equal(store.timeline.length, 7)
  assert.deepEqual(
    store.timeline.map((event) => event.type),
    [
      'content_evidence_observed',
      'visual_evidence_observed',
      'prosody_evidence_observed',
      'profile_updated',
      'prediction_generated',
      'locked',
      'robot_response',
    ]
  )
})

test('a feedback snapshot records the previous response, evaluation and belief update', () => {
  setActivePinia(createPinia())
  const store = useHiwmStore()
  store.beginSession('session-replay')
  const withFeedback = snapshot()
  withFeedback.feedback = {
    previous_turn_id: 'turn-0',
    actual_observation: '用户确认需要先核对交付时间。',
    comparison: 'partial',
    explanation: '确认了核对动作，但具体日期仍未确定。',
    evidence_refs: ['asr:turn-1'],
  }

  store.consumeAvatarMetadata({ hiwm: withFeedback })

  assert.equal(store.error, '')
  assert.equal(store.timeline.length, 9)
  assert.deepEqual(
    store.timeline.map((event) => event.type),
    [
      'content_evidence_observed',
      'visual_evidence_observed',
      'prosody_evidence_observed',
      'actual_response',
      'evaluated',
      'profile_updated',
      'prediction_generated',
      'locked',
      'robot_response',
    ]
  )
  const actual = store.timeline.find((event) => event.type === 'actual_response')
  assert.deepEqual(actual?.payload, {
    previous_turn_id: 'turn-0',
    content: '用户确认需要先核对交付时间。',
    evidence_refs: ['asr:turn-1'],
  })
  const evaluated = store.timeline.find((event) => event.type === 'evaluated')
  assert.deepEqual(evaluated?.payload, {
    previous_turn_id: 'turn-0',
    comparison: 'partial',
    explanation: '确认了核对动作，但具体日期仍未确定。',
  })
})

test('two or four action snapshots are rejected without overwriting accepted history', () => {
  for (const actionCount of [2, 4]) {
    setActivePinia(createPinia())
    const store = useHiwmStore()
    store.beginSession('session-replay')
    store.consumeAvatarMetadata({ hiwm: snapshot() })
    const acceptedEventIds = store.timeline.map((event) => event.event_id)
    const invalid = structuredClone(snapshot())
    if (actionCount === 2) {
      invalid.actions = invalid.actions.slice(0, 2)
    } else {
      invalid.actions.push({
        ...invalid.actions[0],
        action_id: 'action-4',
        strategy: 'ask_for_date',
        utterance: '请提供具体交付日期。',
        predicted_observation: '用户可能提供日期。',
        risk: '可能暂时无法确定日期。',
      })
    }

    store.consumeAvatarMetadata({ hiwm: invalid })

    assert.equal(store.error, '分析结果格式暂时无法识别')
    assert.equal(store.turnId, '')
    assert.deepEqual(
      store.timeline.map((event) => event.event_id),
      acceptedEventIds
    )
  }
})

test('timeline rejects an evidence event that attempts to persist a raw media field', () => {
  setActivePinia(createPinia())
  const store = useHiwmStore()
  store.beginSession('session-replay')
  const valid = buildTimelineEvents(snapshot())[1]
  const invalid = {
    ...valid,
    event_id: `${valid.event_id}:invalid`,
    payload: {
      ...valid.payload,
      measurements: { image: 'data:image/jpeg;base64,forbidden' },
    },
  } as HiwmTimelineEvent
  const disguisedRawMedia = {
    ...valid,
    event_id: `${valid.event_id}:disguised`,
    payload: {
      ...valid.payload,
      measurements: { artifact: 'data:image/jpeg;base64,forbidden' },
    },
  } as HiwmTimelineEvent

  store.appendTimelineEvents('session-replay', [invalid, disguisedRawMedia])

  assert.equal(store.timeline.length, 0)
})
