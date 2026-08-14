import '@fontsource/m-plus-1/400.css'
import '@fontsource/m-plus-1/700.css'
import './style.css'
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'

const pinia = createPinia()
createApp(App).use(pinia).mount('#app')
