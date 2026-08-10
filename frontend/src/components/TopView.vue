<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useGameStore } from '../store/game'
import type { Settings } from '../types'
import RuleSettingsForm from './RuleSettingsForm.vue'

const store = useGameStore()

const dedicatedRoomId = ref<string | null>(null)
const joinRoomId = ref('')
const joinName = ref('')
const joinPassword = ref('')
const needsPassword = ref(false)
const checkedRoomId = ref<string | null>(null)
const roomNotFound = ref(false)
const isChecking = ref(false)
const isJoining = ref(false)
const isCreating = ref(false)

// 編集中の設定
const draft = ref<Settings>({ ...store.draftSettings })

watch(
  () => store.draftSettings,
  (s) => {
    draft.value = { ...s }
  },
  { immediate: true },
)

onMounted(() => {
  const pathRoomId = extractRoomIdFromPath()
  if (pathRoomId) {
    dedicatedRoomId.value = pathRoomId
    joinRoomId.value = pathRoomId
    void onCheckRoom()
  }
})

function extractRoomIdFromPath(): string {
  const parts = window.location.pathname.split('/').filter(Boolean)
  const last = parts[parts.length - 1]
  if (parts.length >= 2 && parts[0] === 'game' && last) {
    return last
  }
  return ''
}

function resetJoin(clearError = true): void {
  joinRoomId.value = ''
  checkedRoomId.value = null
  roomNotFound.value = false
  needsPassword.value = false
  joinPassword.value = ''
  dedicatedRoomId.value = null
  if (window.location.pathname.startsWith('/game/')) {
    window.history.pushState(null, '', '/')
  }
  if (clearError) {
    store.clearError()
  }
}

function onResetJoin(): void {
  resetJoin(true)
}


async function onCreateRoom(): Promise<void> {
  store.draftSettings = { ...draft.value }
  isCreating.value = true
  store.clearError()
  try {
    await store.createRoom()
  } finally {
    isCreating.value = false
  }
}

async function onCheckRoom(): Promise<void> {
  const id = extractRoomId(joinRoomId.value)
  if (!id) {
    store.errorMessage = 'ルームIDまたはURLを入力してください。'
    return
  }
  isChecking.value = true
  roomNotFound.value = false
  store.clearError()
  try {
    // 再接続Cookieがあれば名前入力をスキップして即座に復帰する
    const reconnected = await store.tryReconnect(id)
    if (reconnected) {
      return
    }

    const info = await store.checkRoomInfo(id)
    if (!info.exists) {
      resetJoin(false)
      store.errorMessage = '部屋が見つかりませんでした。'
      return
    }
    checkedRoomId.value = id
    needsPassword.value = info.hasPassword
  } catch {
    resetJoin(false)
    store.errorMessage = '部屋が見つかりませんでした。'
  } finally {
    isChecking.value = false
  }
}


async function onJoinRoom(): Promise<void> {
  const id = checkedRoomId.value ?? extractRoomId(joinRoomId.value)
  if (!id) {
    store.errorMessage = 'ルームIDまたはURLを入力してください。'
    return
  }
  const name = joinName.value.trim()
  if (!name) {
    store.errorMessage = '名前を入力してください。'
    return
  }
  isJoining.value = true
  store.clearError()
  try {
    await store.joinRoom(id, name, needsPassword.value ? joinPassword.value : null)
  } finally {
    isJoining.value = false
  }
}

function extractRoomId(input: string): string {
  const trimmed = input.trim()
  if (!trimmed) return ''
  // URL の場合は最後のパス要素をルームID とみなす
  try {
    const url = new URL(trimmed)
    const parts = url.pathname.split('/').filter(Boolean)
    return parts[parts.length - 1] ?? trimmed
  } catch {
    return trimmed
  }
}
</script>

<template>
  <div class="top-view">
    <!-- 専用URL直接アクセス時 -->
    <template v-if="dedicatedRoomId">
      <div v-if="store.isRestoringRoom || isChecking" class="dedicated-status">
        <p class="notice info">ルームに接続しています…</p>
      </div>

      <div v-else-if="roomNotFound" class="panel setup-panel dedicated-card">
        <header class="screen-header">
          <div>
            <h2>ルームが見つかりません</h2>
            <p>指定されたルームは存在しないか、終了した可能性があります。</p>
          </div>
          <div class="header-mark">ビンゴ</div>
        </header>
        <p class="notice error mb-4">ルームが存在しません。</p>
        <button type="button" class="primary-button" @click="onResetJoin">
          トップページへ戻る
        </button>
      </div>

      <div v-else-if="checkedRoomId" class="panel setup-panel dedicated-card">
        <header class="screen-header">
          <div>
            <h2>ルームに参加</h2>
            <p>名前を入力してゲームに参加してください。</p>
          </div>
          <div class="header-mark">ビンゴ</div>
        </header>

        <p v-if="store.errorMessage" class="notice error mb-4">{{ store.errorMessage }}</p>

        <div class="settings-form">
          <fieldset class="panel-fieldset">
            <legend class="panel-legend">参加者名</legend>
            <div class="field">
              <label for="dedicatedJoinName" class="field-label">参加者名</label>
              <input
                id="dedicatedJoinName"
                v-model="joinName"
                type="text"
                class="text-input"
                placeholder="名前を入力"
                autofocus
                @keydown.enter="onJoinRoom"
              >
            </div>
            <div v-if="needsPassword" class="field mt-3">
              <label for="dedicatedJoinPassword" class="field-label">合言葉・パスワード</label>
              <input
                id="dedicatedJoinPassword"
                v-model="joinPassword"
                type="password"
                class="text-input"
                placeholder="パスワードを入力"
                @keydown.enter="onJoinRoom"
              >
            </div>
          </fieldset>

          <div class="settings-actions">
            <button
              type="button"
              class="primary-button"
              :disabled="isJoining"
              @click="onJoinRoom"
            >
              {{ isJoining ? '参加中…' : '参加する' }}
            </button>
            <button type="button" class="secondary-button ml-4" @click="onResetJoin">
              トップへ戻る
            </button>
          </div>
        </div>
      </div>
    </template>

    <!-- 通常トップ画面 -->
    <template v-else>
      <header class="screen-header">
        <div>
          <h1>しりとりビンゴ</h1>
        </div>
        <div class="header-mark">ビンゴ</div>
      </header>

      <p v-if="store.noticeMessage" class="notice info mb-4">
        {{ store.noticeMessage }}
      </p>

      <p v-if="store.errorMessage" class="notice error mb-4">
        {{ store.errorMessage }}
      </p>


      <v-row>
        <!-- ルーム参加パネル（左：幅1） -->
        <v-col cols="12" md="4">
          <section class="panel setup-panel join-panel">
            <div class="section-heading">
              <h2>ルームに参加</h2>
              <p>作成済みのルームIDまたはURLから参加します</p>
            </div>

            <div v-if="roomNotFound" class="join-content">
              <p class="notice error mb-3">ルームが存在しません。</p>
              <button type="button" class="primary-button" @click="onResetJoin">
                再入力する
              </button>
            </div>

            <div v-else class="join-content">
              <div class="field mb-3">
                <label for="joinRoomId" class="field-label">ルームURLまたはルームID</label>
                <input
                  id="joinRoomId"
                  v-model="joinRoomId"
                  type="text"
                  class="text-input"
                  placeholder="例: room-abc1234"
                  :disabled="!!checkedRoomId"
                >
              </div>

              <div v-if="!checkedRoomId">
                <button
                  type="button"
                  class="secondary-button"
                  :disabled="isChecking || !joinRoomId.trim()"
                  @click="onCheckRoom"
                >
                  {{ isChecking ? '確認中…' : 'ルームを確認' }}
                </button>
              </div>

              <template v-if="checkedRoomId">
                <p class="notice success mb-3">
                  ルームが見つかりました。参加者名を入力してください。
                </p>

                <div v-if="needsPassword" class="field mb-3">
                  <label for="joinPassword" class="field-label">パスワード</label>
                  <input
                    id="joinPassword"
                    v-model="joinPassword"
                    type="password"
                    class="text-input"
                  >
                </div>

                <div class="field mb-3">
                  <label for="joinName" class="field-label">参加者名</label>
                  <input
                    id="joinName"
                    v-model="joinName"
                    type="text"
                    class="text-input"
                    placeholder="名前を入力"
                    @keydown.enter="onJoinRoom"
                  >
                </div>

                <div class="settings-actions">
                  <button
                    type="button"
                    class="primary-button"
                    :disabled="isJoining || !joinName.trim()"
                    @click="onJoinRoom"
                  >
                    {{ isJoining ? '参加中…' : '参加する' }}
                  </button>
                  <button type="button" class="secondary-button ml-4" @click="onResetJoin">
                    キャンセル
                  </button>
                </div>
              </template>
            </div>
          </section>
        </v-col>

        <!-- ルール設定＆ルーム作成パネル（右：幅2） -->
        <v-col cols="12" md="8">
          <section class="panel setup-panel">
            <div class="section-heading">
              <h2>ルール設定</h2>
              <p>ゲームのルールやカードサイズを設定します</p>
            </div>

            <RuleSettingsForm
              v-model="draft"
              submit-button-text="ルームを作成"
              :is-submitting="isCreating"
              @submit="onCreateRoom"
            />
          </section>
        </v-col>
      </v-row>
    </template>
  </div>
</template>

<style scoped>
.top-view {
  display: grid;
  gap: 20px;
}

.join-panel {
  position: sticky;
  top: 16px;
}

.dedicated-card {
  max-width: 580px;
  margin: 32px auto 0;
}

.dedicated-status {
  max-width: 480px;
  margin: 64px auto 0;
  text-align: center;
}

.mb-3 { margin-bottom: 12px; }
.mb-4 { margin-bottom: 16px; }
.mt-3 { margin-top: 12px; }
.ml-4 { margin-left: 16px; }

@media (max-width: 960px) {
  .join-panel {
    position: static;
  }
}
</style>
