export const COMPANION_SESSION_KEY = 'hiwm.companion.session.v1'

type SessionStorage = {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
}

export function loadOrCreateCompanionSession(
  storage: SessionStorage | undefined,
  createId: () => string
): string {
  if (!storage) return createId()
  const existing = storage.getItem(COMPANION_SESSION_KEY)
  if (existing) return existing
  const created = createId()
  storage.setItem(COMPANION_SESSION_KEY, created)
  return created
}

export function replaceCompanionSession(
  storage: SessionStorage | undefined,
  createId: () => string
): string {
  const created = createId()
  storage?.setItem(COMPANION_SESSION_KEY, created)
  return created
}
