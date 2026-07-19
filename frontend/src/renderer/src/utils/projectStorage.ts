/** Browser storage owned by HIWM, with one-way migration from pre-0.2 keys. */

export const HIWM_AUTH_STORAGE_KEY = 'hiwm.runtime-control.auth.v1'
export const HIWM_TIMELINE_STORAGE_KEY = 'hiwm.timeline.v1'
export const HIWM_PROFILE_STORAGE_KEY = 'hiwm.initial-profile.v1'

export const LEGACY_AUTH_STORAGE_KEYS = ['auth_openavatarchat'] as const
export const LEGACY_TIMELINE_STORAGE_KEYS = ['openavatarchat.hiwm.timeline.v1'] as const
export const LEGACY_PROFILE_STORAGE_KEYS = ['openavatarchat.hiwm.initial-profile.v1'] as const

const storageAvailable = (): boolean =>
  typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'

const removeStorageKey = (key: string): void => {
  if (typeof window.localStorage.removeItem === 'function') {
    window.localStorage.removeItem(key)
  }
}

export function readMigratedStorage(
  key: string,
  legacyKeys: readonly string[] = []
): string | null {
  if (!storageAvailable()) return null
  try {
    const current = window.localStorage.getItem(key)
    if (current !== null) return current
    for (const legacyKey of legacyKeys) {
      const legacy = window.localStorage.getItem(legacyKey)
      if (legacy === null) continue
      window.localStorage.setItem(key, legacy)
      removeStorageKey(legacyKey)
      return legacy
    }
  } catch {
    return null
  }
  return null
}

export function writeProjectStorage(
  key: string,
  value: string,
  legacyKeys: readonly string[] = []
): void {
  if (!storageAvailable()) return
  window.localStorage.setItem(key, value)
  for (const legacyKey of legacyKeys) removeStorageKey(legacyKey)
}

export function removeProjectStorage(key: string, legacyKeys: readonly string[] = []): void {
  if (!storageAvailable()) return
  removeStorageKey(key)
  for (const legacyKey of legacyKeys) removeStorageKey(legacyKey)
}

export const readRuntimeControlToken = (): string =>
  readMigratedStorage(HIWM_AUTH_STORAGE_KEY, LEGACY_AUTH_STORAGE_KEYS) || ''

export const writeRuntimeControlToken = (token: string): void => {
  const normalized = token.trim()
  if (normalized) {
    writeProjectStorage(HIWM_AUTH_STORAGE_KEY, normalized, LEGACY_AUTH_STORAGE_KEYS)
  } else {
    removeProjectStorage(HIWM_AUTH_STORAGE_KEY, LEGACY_AUTH_STORAGE_KEYS)
  }
}
