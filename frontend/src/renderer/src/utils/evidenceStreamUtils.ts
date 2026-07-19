export type EvidenceRecord = Record<string, unknown>

export const isDisplayableChatRecord = (record: EvidenceRecord): boolean =>
  record.invalid !== true && record.cancelled !== true
