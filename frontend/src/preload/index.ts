import { contextBridge, ipcRenderer } from 'electron'
import { electronAPI } from '@electron-toolkit/preload'

// Custom APIs for renderer
const api = {}

// Use `contextBridge` APIs to expose Electron APIs to
// renderer only if context isolation is enabled, otherwise
// just add to the DOM global.
if (process.contextIsolated) {
  try {
    contextBridge.exposeInMainWorld('electron', electronAPI)
    contextBridge.exposeInMainWorld('api', api)
    contextBridge.exposeInMainWorld('electronInfo', {
      version: process.version,
      platform: process.platform,
    })
    contextBridge.exposeInMainWorld('safeApi', {
      fetch: (url: string, options?: RequestInit) => {
        const requestedMethod = options?.method?.toUpperCase() || 'GET'
        const method = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD'].includes(requestedMethod)
          ? requestedMethod
          : 'OTHER'
        console.debug('Electron safe fetch requested', { method })
        return ipcRenderer.invoke('safe-fetch', { url, options })
      },
    })
  } catch (error) {
    console.error('Electron preload initialization failed', {
      errorName: error instanceof Error && error.name ? error.name : 'UnknownError',
    })
  }
} else {
  // @ts-ignore (define in dts)
  window.electron = electronAPI
  // @ts-ignore (define in dts)
  window.electronInfo = {
    version: process.version,
    platform: process.platform,
  }
  // @ts-ignore (define in dts)
  window.api = api
}
console.debug('Electron preload ready', { contextIsolated: Boolean(process.contextIsolated) })

document.addEventListener('DOMContentLoaded', () => {
  const app = document.getElementById('app')
  if (app) {
    app.addEventListener('contextmenu', (event) => {
      event.preventDefault()
      ipcRenderer.send('show-context-menu')
    })
  }
})
