<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useConfirm } from '../composables/useConfirm'

withDefaults(
  defineProps<{
    disableTeleport?: boolean
  }>(),
  {
    disableTeleport: false,
  },
)

const { state, handleConfirm, handleCancel } = useConfirm()
const confirmButtonRef = ref<HTMLButtonElement | null>(null)

function onKeyDown(e: KeyboardEvent): void {
  if (!state.value.isOpen)
    return
  if (e.key === 'Escape') {
    e.preventDefault()
    handleCancel()
  }
}

watch(
  () => state.value.isOpen,
  async (isOpen) => {
    if (isOpen) {
      await nextTick()
      confirmButtonRef.value?.focus()
    }
  },
)

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
})
</script>

<template>
  <Teleport to="body" :disabled="disableTeleport">
    <Transition name="confirm-fade">
      <div
        v-if="state.isOpen"
        class="confirm-modal-backdrop"
        role="dialog"
        aria-modal="true"
        :aria-label="state.title"
        @click.self="handleCancel"
      >
        <div class="confirm-modal-card">
          <h2 class="confirm-modal-title">
            {{ state.title }}
          </h2>
          <p class="confirm-modal-message">
            {{ state.message }}
          </p>
          <div class="confirm-modal-actions">
            <button
              type="button"
              class="secondary-button modal-cancel-button"
              @click="handleCancel"
            >
              {{ state.cancelText }}
            </button>
            <button
              ref="confirmButtonRef"
              type="button"
              class="modal-confirm-button" :class="[state.danger ? 'danger-button' : 'primary-button']"
              @click="handleConfirm"
            >
              {{ state.confirmText }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.confirm-modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(16, 43, 57, 0.65);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  z-index: 9999;
}

.confirm-modal-card {
  background: var(--panel, #fffdf8);
  border: 2px solid var(--navy, #17384a);
  box-shadow: 6px 6px 0 var(--navy, #17384a);
  border-radius: 20px;
  width: 100%;
  max-width: 440px;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  animation: confirmPop 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes confirmPop {
  from {
    opacity: 0;
    transform: scale(0.95) translateY(8px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

.confirm-modal-title {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 900;
  color: var(--navy-deep, #102b39);
  letter-spacing: -0.01em;
}

.confirm-modal-message {
  margin: 0;
  font-size: 0.95rem;
  line-height: 1.6;
  color: var(--ink, #17232d);
  white-space: pre-line;
}

.confirm-modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 8px;
}

.confirm-modal-actions button {
  min-width: 100px;
}

.confirm-fade-enter-active,
.confirm-fade-leave-active {
  transition: opacity 0.2s ease;
}

.confirm-fade-enter-from,
.confirm-fade-leave-to {
  opacity: 0;
}
</style>
