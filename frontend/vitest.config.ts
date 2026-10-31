/* eslint-disable node/prefer-global/process */
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

// Node.js 22+ の native localStorage が jsdom の localStorage をシャドウイングする問題への対策
const nodeProcess = (globalThis as Record<string, any>).process
const nodeVersion = typeof nodeProcess?.versions?.node === 'string' ? nodeProcess.versions.node : ''
const nodeMajor = Number(nodeVersion.split('.')[0] || 0)
const webStorageFlag = nodeMajor >= 25 ? '--no-webstorage' : '--no-experimental-webstorage'
const execArgv = nodeMajor >= 22 ? [webStorageFlag] : []

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    poolOptions: {
      threads: {
        execArgv,
      },
      forks: {
        execArgv,
      },
    },
    coverage: {
      reporter: ['text', 'json', 'html'],
    },
  },
})
