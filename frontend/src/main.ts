import { createPinia } from 'pinia'
import { createApp } from 'vue'
import App from './App.vue'
import '@fontsource/m-plus-1/400.css'
import '@fontsource/m-plus-1/700.css'
import './style.css'

const pinia = createPinia()
createApp(App).use(pinia).mount('#app')
