export type CompanionExample = {
  id: string
  name: string
  tagline: string
  description: string
  prompt_suggestions: string[]
}

export type CompanionExampleCatalog = {
  examples: CompanionExample[]
  defaultExampleId: string
}

const SAFE_ID = /^[A-Za-z0-9_.-]+$/

function cleanText(value: unknown, maximum: number): string {
  return typeof value === 'string' ? value.trim().slice(0, maximum) : ''
}

function fallbackExample(id: string): CompanionExample {
  return {
    id,
    name: '默认陪伴',
    tagline: '从一段真实对话开始',
    description: '随着交流逐步熟悉你的表达习惯和沟通偏好。',
    prompt_suggestions: ['最近我想聊聊自己的状态。'],
  }
}

/**
 * Keep only the public fields used by the showcase. Extra server fields are
 * deliberately discarded so implementation metadata can never reach a view.
 */
export function parseCompanionExampleCatalog(
  payload: unknown,
  fallbackUserId = 'showcase-anchor'
): CompanionExampleCatalog {
  const body = payload && typeof payload === 'object' ? (payload as Record<string, unknown>) : {}
  const rawExamples = Array.isArray(body.examples) ? body.examples : []
  const seen = new Set<string>()
  const examples: CompanionExample[] = []

  for (const raw of rawExamples) {
    if (!raw || typeof raw !== 'object') continue
    const item = raw as Record<string, unknown>
    const id = cleanText(item.id, 256)
    const name = cleanText(item.name, 40)
    const tagline = cleanText(item.tagline, 80)
    const description = cleanText(item.description, 240)
    if (!id || !SAFE_ID.test(id) || seen.has(id) || !name || !tagline || !description) continue

    seen.add(id)
    examples.push({
      id,
      name,
      tagline,
      description,
      prompt_suggestions: (Array.isArray(item.prompt_suggestions) ? item.prompt_suggestions : [])
        .map((value) => cleanText(value, 160))
        .filter(Boolean)
        .slice(0, 4),
    })
  }

  const safeFallbackId =
    SAFE_ID.test(fallbackUserId) && fallbackUserId.length <= 256
      ? fallbackUserId
      : 'showcase-anchor'
  if (!examples.length) examples.push(fallbackExample(safeFallbackId))

  const requestedDefault = cleanText(body.default_example_id, 256)
  const defaultExampleId = examples.some((item) => item.id === requestedDefault)
    ? requestedDefault
    : examples[0].id

  return { examples, defaultExampleId }
}
