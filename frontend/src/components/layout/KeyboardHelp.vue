<script setup lang="ts">
defineEmits<{
  close: []
}>()

const globalShortcuts = [
  { key: '?', description: 'Toggle this help' },
  { key: 'v', description: 'Cycle layout mode (River / Reader)' },
  { key: 'Escape', description: 'Close overlay / go back' },
]

const riverShortcuts = [
  { key: 'j / k', description: 'Next / previous section' },
  { key: 'u / d', description: 'Upvote / downvote focused section' },
  { key: 'o', description: 'Open article in new tab' },
]
</script>

<template>
  <Teleport to="body">
    <div
      class="help-backdrop"
      @click="$emit('close')"
    >
      <div
        class="help-panel"
        @click.stop
      >
        <div class="help-header">
          <h2 class="help-title">Keyboard shortcuts</h2>
          <button
            class="help-close"
            aria-label="Close"
            @click="$emit('close')"
          >
            &times;
          </button>
        </div>
        <h3 class="help-section-title">Global</h3>
        <table class="help-table">
          <tbody>
            <tr
              v-for="s in globalShortcuts"
              :key="s.key"
            >
              <td class="help-key">
                <kbd>{{ s.key }}</kbd>
              </td>
              <td class="help-desc">{{ s.description }}</td>
            </tr>
          </tbody>
        </table>
        <h3 class="help-section-title">Triage (River mode)</h3>
        <table class="help-table">
          <tbody>
            <tr
              v-for="s in riverShortcuts"
              :key="s.key"
            >
              <td class="help-key">
                <kbd>{{ s.key }}</kbd>
              </td>
              <td class="help-desc">{{ s.description }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.help-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9000;
}

.help-panel {
  background: var(--pq-bg);
  border: 1px solid var(--pq-border);
  border-radius: calc(var(--pq-radius) * 2);
  padding: 1.5rem;
  min-width: 20rem;
  max-width: 28rem;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}

.help-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
}

.help-title {
  font-size: 1rem;
  font-weight: 600;
  margin: 0;
  color: var(--pq-text);
}

.help-section-title {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--pq-muted);
  margin: 0.75rem 0 0.25rem;
}

.help-section-title:first-of-type {
  margin-top: 0;
}

.help-close {
  background: none;
  border: none;
  color: var(--pq-muted);
  font-size: 1.25rem;
  cursor: pointer;
  padding: 0;
  line-height: 1;
}
.help-close:hover {
  color: var(--pq-text);
}

.help-table {
  width: 100%;
  border-collapse: collapse;
}

.help-table tr + tr {
  border-top: 1px solid var(--pq-border);
}

.help-table td {
  padding: 0.5rem 0;
}

.help-key {
  width: 5rem;
}

.help-key kbd {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  font-family: var(--pq-font-mono);
  font-size: 0.8rem;
  background: var(--pq-card-bg);
  border: 1px solid var(--pq-border);
  border-radius: var(--pq-radius);
  color: var(--pq-text);
}

.help-desc {
  color: var(--pq-muted);
  font-size: 0.875rem;
}

.help-hint {
  margin: 1rem 0 0;
  font-size: 0.75rem;
  color: var(--pq-muted);
}
</style>
