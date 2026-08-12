import '@fontsource/m-plus-1/400.css'
import '@fontsource/m-plus-1/700.css'
import '@mdi/font/css/materialdesignicons.css'
import 'vuetify/styles'
import './style.css'
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import App from './App.vue'

const vuetify = createVuetify({
  components,
  directives,
  theme: {
    defaultTheme: 'shiritoriTheme',
    themes: {
      shiritoriTheme: {
        dark: false,
        colors: {
          primary: '#df684f', // var(--coral)
          secondary: '#1c8b86', // var(--teal)
          navy: '#17384a',
          warning: '#edb84d',
          error: '#a7302c',
          background: '#f5f1e8',
          surface: '#fffdf8',
        },
      },
    },
  },
})

const pinia = createPinia()
createApp(App).use(pinia).use(vuetify).mount('#app')
