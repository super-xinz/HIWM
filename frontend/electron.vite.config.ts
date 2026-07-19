import { resolve, join } from 'path'
import { defineConfig, externalizeDepsPlugin } from 'electron-vite'
import viteConfig from './vite.config'

const baseOutDir = join(__dirname, 'dist-electron/out')
export default defineConfig({
  main: {
    build: {
      outDir: join(baseOutDir, 'main'),
    },
    plugins: [externalizeDepsPlugin()],
  },
  preload: {
    plugins: [externalizeDepsPlugin()],
    build: {
      outDir: join(baseOutDir, 'preload'),
      rollupOptions: {
        output: {
          format: 'es',
        },
      },
    },
  },
  renderer: {
    build: {
      outDir: join(baseOutDir, 'renderer'),
    },
    resolve: {
      alias: {
        '@renderer': resolve('src/renderer/src'),
        '@': resolve('src/renderer/src'),
      },
    },
    define: viteConfig.define,
    plugins: viteConfig.plugins,
    server: viteConfig.server,
  },
})
