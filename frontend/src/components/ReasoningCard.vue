<script setup>
defineProps({
  title: {
    type: String,
    default: "查看思考过程",
  },
  items: {
    type: Array,
    default: () => [],
  },
});
</script>

<template>
  <details class="reasoning-card">
    <summary>{{ title }}</summary>
    <ul>
      <li v-for="item in items" :key="item">{{ item }}</li>
    </ul>
  </details>
</template>

<style scoped>
.reasoning-card {
  margin-top: 14px;
  padding: 14px 16px;
  border: 1px dashed rgba(37, 99, 235, 0.22);
  border-radius: 18px;
  background: rgba(245, 248, 255, 0.92);
}

summary {
  cursor: pointer;
  color: var(--accent-strong);
  font-weight: 700;
}

ul {
  margin: 12px 0 0;
  padding-left: 18px;
  color: var(--text-soft);
  line-height: 1.75;
}
</style>
