<template>
  <span
    class="disconnected-mark"
    aria-label="切断中"
    title="切断中"
  >
    <span class="mdi mdi-wifi-off" aria-hidden="true" />
  </span>
</template>

<style scoped>
.disconnected-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-left: 4px;
  color: var(--danger);
  font-size: 0.9em;
  vertical-align: 0.04em;
}
</style>
