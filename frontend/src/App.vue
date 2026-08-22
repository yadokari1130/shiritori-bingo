<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useGameStore } from './store/game'
import * as api from './api'
import TopView from './components/TopView.vue'
import LobbyView from './components/LobbyView.vue'
import PlayingView from './components/PlayingView.vue'
import ResultView from './components/ResultView.vue'
import ConfirmModal from './components/ConfirmModal.vue'

const store = useGameStore()

function handleUnload() {
  if (store.roomId) {
    api.notifyDisconnect(store.roomId)
  }
  store.disconnectSse()
}

onMounted(() => {
  window.addEventListener('pagehide', handleUnload)
  window.addEventListener('beforeunload', handleUnload)
})

onUnmounted(() => {
  window.removeEventListener('pagehide', handleUnload)
  window.removeEventListener('beforeunload', handleUnload)
})
</script>

<template>
  <div class="app-root">
    <div class="main-content">
      <main class="app-shell">
        <TopView v-if="store.view === 'top'" />
        <LobbyView v-else-if="store.view === 'lobby'" />
        <PlayingView v-else-if="store.view === 'playing'" />
        <ResultView v-else-if="store.view === 'result'" />
      </main>
    </div>
    <ConfirmModal />
  </div>
</template>

<style scoped>
.app-root {
  background: transparent !important;
}

.app-nav-bar {
  background: rgba(23, 56, 74, 0.95) !important;
  color: #ffffff !important;
  border-bottom: 2px solid #102b39;
  backdrop-filter: blur(8px);
}

.app-title {
  font-weight: 900;
  letter-spacing: 0.06em;
  color: #fffdf8;
}

.title-text {
  font-size: 1.15rem;
}

.connection-chip {
  font-weight: 700;
  font-size: 0.8rem;
}

.main-content {
  min-height: 100vh;
}
</style>

