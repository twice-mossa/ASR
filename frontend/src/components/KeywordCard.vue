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
  margin-top: 14px;
  padding: 18px;
  border: 1px solid var(--line-soft);
  border-radius: 20px;
  background: white;
}

.label {
  margin: 0 0 6px;
  color: var(--text-soft);
  font-size: 0.74rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

h4 {
  margin: 0;
  color: var(--text-strong);
  font-size: 1.06rem;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
}

.tag-item {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0 12px;
  border-radius: 999px;
  background: #eef4ff;
  color: #1f49b6;
  font-weight: 700;
}
</style>
