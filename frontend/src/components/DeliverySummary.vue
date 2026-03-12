<script setup>
defineProps({
  label: {
    type: String,
    default: "交付说明",
  },
  title: {
    type: String,
    default: "这次实现了什么",
  },
  items: {
    type: Array,
    default: () => [],
  },
});
</script>

<template>
  <article class="card">
    <p class="card-label">{{ label }}</p>
    <h2>{{ title }}</h2>
    <ul class="feature-list">
      <li v-for="item in items" :key="item">{{ item }}</li>
    </ul>
  </article>
</template>

<style scoped>
.card {
  padding: 24px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.82);
  box-shadow: 0 18px 60px rgba(48, 60, 80, 0.12);
  backdrop-filter: blur(10px);
}

.card-label {
  margin: 0 0 10px;
  color: #915f00;
  font-size: 0.9rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

h2 {
  margin: 0 0 16px;
  font-size: 1.45rem;
}

.feature-list {
  margin: 0;
  padding-left: 20px;
  line-height: 1.9;
}
</style>
