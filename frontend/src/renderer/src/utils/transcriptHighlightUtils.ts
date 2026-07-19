export type TaskSignalForHighlight = {
  id: string
  category: 'need' | 'concern' | 'commitment' | 'question' | 'unknown'
  statement: string
}

export type TranscriptTextSegment = {
  text: string
  highlighted: boolean
  category?: TaskSignalForHighlight['category']
  signalId?: string
}

type MatchRange = {
  start: number
  end: number
  category: TaskSignalForHighlight['category']
  signalId: string
}

const genericCandidates = new Set([
  '用户',
  '客户',
  '对方',
  '来访者',
  '说话者',
  '当前',
  '问题',
  '信息',
  '内容',
  '未知',
  '表示',
  '提到',
  '说明',
])

const trimCandidate = (value: string): string =>
  value
    .trim()
    .replace(/^[\s“”‘’"'「」『』（）()【】]+|[\s“”‘’"'「」『』（）()【】]+$/gu, '')
    .trim()

const hasEnoughMeaningfulCharacters = (value: string): boolean => {
  if (genericCandidates.has(value)) return false
  const meaningful = value.match(/[\p{Letter}\p{Number}]/gu)?.length ?? 0
  const containsCjk = /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}]/u.test(value)
  return containsCjk ? meaningful >= 2 : meaningful >= 4
}

const signalCandidates = (statement: string): string[] => {
  const rawCandidates = new Set<string>([statement])

  for (const match of statement.matchAll(/[“"「『]([^”"」』]{2,120})[”"」』]/gu)) {
    rawCandidates.add(match[1])
  }

  for (const clause of statement.split(/[，,。；;！!？?\n]+/u)) {
    rawCandidates.add(clause)
    rawCandidates.add(
      clause.replace(
        /^(?:(?:用户|客户|对方|来访者|说话者)\s*)?(?:(?:明确|再次|仍然|已经|当前|主动|直接)\s*)*(?:表示|提到|说明|反馈|询问|问到|确认)\s*[：:,，]?\s*/u,
        ''
      )
    )
  }

  return [...rawCandidates]
    .map(trimCandidate)
    .filter(hasEnoughMeaningfulCharacters)
    .sort((left, right) => right.length - left.length)
}

const escapeRegExp = (value: string): string => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/**
 * Splits a transcript into plain-text fragments. Only phrases that occur
 * verbatim in a current, structured content signal are marked. Consumers must
 * render `text` via normal text interpolation rather than HTML injection.
 */
export const segmentTaskRelevantTranscript = (
  text: string,
  signals: readonly TaskSignalForHighlight[]
): TranscriptTextSegment[] => {
  if (!text || signals.length === 0) return [{ text, highlighted: false }]

  const ranges: MatchRange[] = []
  const occupied = (start: number, end: number): boolean =>
    ranges.some((range) => start < range.end && end > range.start)

  const candidates = signals
    .flatMap((signal) =>
      signalCandidates(signal.statement).map((candidate) => ({
        candidate,
        category: signal.category,
        signalId: signal.id,
      }))
    )
    .sort((left, right) => right.candidate.length - left.candidate.length)

  for (const { candidate, category, signalId } of candidates) {
    const matcher = new RegExp(escapeRegExp(candidate), 'giu')
    for (const match of text.matchAll(matcher)) {
      const start = match.index
      const end = start + match[0].length
      if (!occupied(start, end)) ranges.push({ start, end, category, signalId })
    }
  }

  if (ranges.length === 0) return [{ text, highlighted: false }]

  ranges.sort((left, right) => left.start - right.start)
  const segments: TranscriptTextSegment[] = []
  let cursor = 0
  for (const range of ranges) {
    if (range.start > cursor) {
      segments.push({ text: text.slice(cursor, range.start), highlighted: false })
    }
    segments.push({
      text: text.slice(range.start, range.end),
      highlighted: true,
      category: range.category,
      signalId: range.signalId,
    })
    cursor = range.end
  }
  if (cursor < text.length) segments.push({ text: text.slice(cursor), highlighted: false })
  return segments
}
