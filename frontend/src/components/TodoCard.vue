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
      <button class="inline-action" @click="emit('ask')">追问负责人</button>
    </div>
    <ul class="todo-list">
      <li v-for="todo in todos" :key="todo">{{ todo }}</li>
    </ul>
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
  font-size: 0.68rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

h4 {
  margin: 0;
  color: var(--text-strong);
  font-size: 0.98rem;
}

.todo-list {
  margin: 0;
  padding-left: 18px;
  color: var(--text-main);
  line-height: 1.68;
}

.inline-action {
  min-height: 32px;
  padding: 0 11px;
  border: 1px solid var(--line-soft);
  border-radius: 999px;
  background: white;
  color: var(--text-main);
  font-size: 0.8rem;
  font-weight: 700;
  cursor: pointer;
}
</style>
