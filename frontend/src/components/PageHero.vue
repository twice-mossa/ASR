<script setup>
defineProps({
  eyebrow: {
    type: String,
    default: "ASR Meeting Assistant",
  },
  title: {
    type: String,
    default: "智能会议助手",
  },
  intro: {
    type: String,
    default: "先完成账号注册和登录，再逐步接入音频转写、会议纪要、关键词搜索与语音回放。",
  },
  cardLabel: {
    type: String,
    default: "当前阶段",
  },
  cardTitle: {
    type: String,
    default: "登录注册已纳入 Sprint 1",
  },
  projectSteps: {
    type: Array,
    required: true,
  },
});
</script>

<template>
  <section class="hero">
    <div>
      <p class="eyebrow">{{ eyebrow }}</p>
      <h1>{{ title }}</h1>
      <p class="intro">{{ intro }}</p>
    </div>

    <div class="hero-card">
      <p class="card-label">{{ cardLabel }}</p>
      <h2>{{ cardTitle }}</h2>
      <ol>
        <li v-for="step in projectSteps" :key="step">{{ step }}</li>
      </ol>
    </div>
  </section>
</template>

<style scoped>
.hero {
  max-width: 1080px;
  margin: 0 auto 24px;
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(280px, 0.9fr);
  gap: 20px;
  align-items: stretch;
}

.eyebrow,
.card-label {
  margin: 0 0 10px;
  color: #915f00;
  font-size: 0.9rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

h1 {
  margin: 0;
  font-size: clamp(2.6rem, 5vw, 4.6rem);
}

h2 {
  margin: 0 0 16px;
  font-size: 1.45rem;
}

.intro {
  max-width: 720px;
  margin-top: 16px;
  font-size: 1.05rem;
  line-height: 1.8;
}

.hero-card {
  padding: 24px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.82);
  box-shadow: 0 18px 60px rgba(48, 60, 80, 0.12);
  backdrop-filter: blur(10px);
}

.hero-card ol {
  margin: 0;
  padding-left: 20px;
  line-height: 1.9;
}

@media (max-width: 860px) {
  .hero {
    grid-template-columns: 1fr;
  }
}
</style>
