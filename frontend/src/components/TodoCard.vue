<script setup>
defineProps({
  todos: {
    type: Array,
    default: () => [],
  },
});

const emit = defineEmits(["ask"]);
</script>

<template>
  <section class="result-card">
    <div class="card-header">
      <div>
        <p class="label">Action Items</p>
        <h4>待办事项</h4>
      </div>
      <button class="inline-action" @click="emit('ask')">围绕待办继续问</button>
    </div>
    <ul class="todo-list">
      <li v-for="todo in todos" :key="todo">{{ todo }}</li>
    </ul>
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

.card-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 10px;
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

.todo-list {
  margin: 0;
  padding-left: 18px;
  color: var(--text-main);
  line-height: 1.8;
}

.inline-action {
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid var(--line-soft);
  border-radius: 999px;
  background: white;
  color: var(--text-main);
  font-weight: 700;
  cursor: pointer;
}
</style>
