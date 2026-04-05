<script setup lang="ts">
defineProps<{
  tag: string
}>()

defineEmits<{
  downweight: [tag: string]
}>()
</script>

<template>
  <span class="tag-chip">
    <span class="tag-label">{{ tag }}</span>
    <button
      class="tag-downweight"
      :aria-label="`Downweight ${tag}`"
      :title="`Downweight ${tag}`"
      @click.stop="$emit('downweight', tag)"
    >
      &darr;
    </button>
  </span>
</template>

<style scoped>
.tag-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.125rem;
  padding: 0.0625rem 0.375rem;
  background: var(--pq-card-bg);
  border: 1px solid var(--pq-border);
  border-radius: var(--pq-radius);
  font-size: 0.75rem;
  color: var(--pq-muted);
}

.tag-label {
  line-height: 1.4;
}

.tag-downweight {
  background: none;
  border: none;
  color: var(--pq-muted);
  font-size: 0.625rem;
  cursor: pointer;
  padding: 0 0.125rem;
  line-height: 1;
  opacity: 0.35;
  transition: opacity 0.15s;
}

.tag-chip:hover .tag-downweight {
  opacity: 0.6;
}

.tag-downweight:hover {
  opacity: 1;
  color: var(--pq-danger);
}
</style>
