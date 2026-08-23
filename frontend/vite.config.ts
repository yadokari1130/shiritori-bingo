import vue from '@vitejs/plugin-vue'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  const rawSiteUrl = env.VITE_SITE_URL || ''
  const siteUrl = rawSiteUrl.replace(/\/+$/, '')
  const ogUrl = siteUrl ? `${siteUrl}/` : '/'
  const ogImage = siteUrl ? `${siteUrl}/ogp.png` : '/ogp.png'

  return {
    plugins: [
      vue(),
      {
        name: 'html-transform',
        transformIndexHtml(html) {
          return html
            .replaceAll('%OG_URL%', ogUrl)
            .replaceAll('%OG_IMAGE%', ogImage)
        },
      },
    ],
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: 'http://localhost:3001',
          changeOrigin: true,
        },
      },
    },
  }
})
