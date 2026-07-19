import { defineStore } from 'pinia'
import {
  HIWM_PROFILE_STORAGE_KEY,
  LEGACY_PROFILE_STORAGE_KEYS,
  readMigratedStorage,
  removeProjectStorage,
  writeProjectStorage,
} from '../utils/projectStorage.ts'

export type ClientSessionProfilePayload =
  | {
      consent: true
      profile_id: string
      initial_information: string
    }
  | { consent: false }

type StoredProfile = {
  schema_version: '1.0'
  profile_id: string
  initial_information: string
  saved_at: number
}

type ProfileState = {
  profileId: string
  initialInformation: string
  savedAt: number | null
}

const MAX_PROFILE_LENGTH = 4000

const createProfileId = (): string => {
  if (typeof window !== 'undefined' && typeof window.crypto?.randomUUID === 'function') {
    return window.crypto.randomUUID()
  }
  return `profile-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

const loadProfile = (): ProfileState => {
  const fallback = { profileId: createProfileId(), initialInformation: '', savedAt: null }
  if (typeof window === 'undefined' || !window.localStorage) return fallback
  try {
    const serialized = readMigratedStorage(HIWM_PROFILE_STORAGE_KEY, LEGACY_PROFILE_STORAGE_KEYS)
    if (!serialized) return fallback
    const parsed = JSON.parse(serialized) as Partial<StoredProfile>
    if (
      parsed.schema_version !== '1.0' ||
      typeof parsed.profile_id !== 'string' ||
      !/^[A-Za-z0-9_.-]{1,96}$/.test(parsed.profile_id) ||
      typeof parsed.initial_information !== 'string' ||
      parsed.initial_information.length > MAX_PROFILE_LENGTH ||
      typeof parsed.saved_at !== 'number' ||
      !Number.isFinite(parsed.saved_at)
    ) {
      return fallback
    }
    return {
      profileId: parsed.profile_id,
      initialInformation: parsed.initial_information,
      savedAt: parsed.saved_at,
    }
  } catch {
    return fallback
  }
}

export const useProfileStore = defineStore('hiwmProfileStore', {
  state: (): ProfileState => loadProfile(),
  getters: {
    hasProfile: (state): boolean => Boolean(state.initialInformation.trim()),
  },
  actions: {
    save(initialInformation: string): boolean {
      const normalized = initialInformation.trim().slice(0, MAX_PROFILE_LENGTH)
      if (!normalized) return false
      this.initialInformation = normalized
      this.savedAt = Date.now()
      const value: StoredProfile = {
        schema_version: '1.0',
        profile_id: this.profileId,
        initial_information: normalized,
        saved_at: this.savedAt,
      }
      writeProjectStorage(
        HIWM_PROFILE_STORAGE_KEY,
        JSON.stringify(value),
        LEGACY_PROFILE_STORAGE_KEYS
      )
      return true
    },
    clear(): void {
      this.initialInformation = ''
      this.savedAt = null
      this.profileId = createProfileId()
      removeProjectStorage(HIWM_PROFILE_STORAGE_KEY, LEGACY_PROFILE_STORAGE_KEYS)
    },
    toClientPayload(): ClientSessionProfilePayload {
      const initialInformation = this.initialInformation.trim()
      if (!initialInformation) return { consent: false }
      return {
        consent: true,
        profile_id: this.profileId,
        initial_information: initialInformation,
      }
    },
  },
})
