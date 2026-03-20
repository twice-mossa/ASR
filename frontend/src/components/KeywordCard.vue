<script setup>
defineProps({
  keywords: {
    type: Array,
    default: () => [],
  },
});
</script>

<template>
  <section class="result-card">
    <p class="label">Keywords</p>
    <h4>关键词</h4>
    <div class="tag-list">
      <span v-for="keyword in keywords" :key="keyword" class="tag-item">{{ keyword }}</span>
    </div>
  </section>
</template>

<style scoped>
.result-card {
  margin-top: 12px;
  padding: 16px;
  border: 1px solid var(--line-soft);
  border-radius: 18px;
  background: white;
}

.label {
  margin: 0 0 6px;
  color: var(--text-soft);
  font-size: 0.68rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

h4 {
  margin: 0;
  color: var(--text-strong);
  font-size: 0.98rem;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.tag-item {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 11px;
  border-radius: 999px;
  background: #eef4ff;
  color: #1f49b6;
  font-size: 0.8rem;
  font-weight: 700;
}
</style>
