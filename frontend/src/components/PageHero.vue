<script setup>
defineProps({
  eyebrow: {
    type: String,
    default: "ASR Meeting Assistant",
  },
  title: {
    type: String,
    default: "把会议录音整理成真正可用的内容",
  },
  intro: {
    type: String,
    default: "上传录音、生成转写、沉淀摘要和待办，整个过程尽量清晰、顺手、不过度打扰。",
  },
  highlights: {
    type: Array,
    default: () => [],
  },
  notes: {
    type: Array,
    default: () => [],
  },
  metrics: {
    type: Array,
    default: () => [],
  },
});
</script>

<template>
  <section class="hero">
    <div class="copy">
      <div class="eyebrow-row">
        <p class="eyebrow">{{ eyebrow }}</p>
        <span class="eyebrow-badge">Focused Workspace</span>
      </div>

      <h1>{{ title }}</h1>
      <p class="intro">{{ intro }}</p>

      <div class="highlight-grid">
        <article v-for="item in highlights" :key="item.title" class="highlight-card">
          <p>{{ item.title }}</p>
          <span>{{ item.description }}</span>
        </article>
      </div>
    </div>

    <aside class="panel">
      <p class="panel-label">How It Flows</p>

      <div class="metric-grid">
        <div v-for="metric in metrics" :key="metric.label" class="metric-item">
          <strong>{{ metric.value }}</strong>
          <span>{{ metric.label }}</span>
        </div>
      </div>

      <ul class="note-list">
        <li v-for="note in notes" :key="note">{{ note }}</li>
      </ul>
    </aside>
  </section>
</template>

<style scoped>
.hero {
  max-width: 1200px;
  margin: 0 auto 34px;
  display: grid;
  grid-template-columns: minmax(0, 1.42fr) minmax(320px, 0.78fr);
  gap: 24px;
  align-items: stretch;
}

.copy {
  position: relative;
  padding: 28px 6px 16px;
}

.copy::before {
  content: "";
  position: absolute;
  left: -48px;
  top: -38px;
  width: 300px;
  height: 300px;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(96, 165, 250, 0.16) 0%, rgba(96, 165, 250, 0) 72%);
  pointer-events: none;
  filter: blur(12px);
}

.eyebrow-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

.eyebrow,
.panel-label,
.eyebrow-badge {
  margin: 0 0 16px;
  color: rgba(15, 23, 42, 0.52);
  font-size: 0.76rem;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.eyebrow-badge {
  display: inline-flex;
  align-items: center;
  padding: 8px 12px;
  margin-bottom: 16px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.6);
  color: #1d4ed8;
  letter-spacing: 0.12em;
  backdrop-filter: blur(14px);
}

h1 {
  margin: 0;
  max-width: 10ch;
  font-family: "Inter", "SF Pro Display", "PingFang SC", "Helvetica Neue", sans-serif;
  font-size: clamp(3.6rem, 7vw, 6.2rem);
  font-weight: 800;
  line-height: 0.92;
  letter-spacing: -0.04em;
  text-wrap: balance;
  color: #0f172a;
}

.intro {
  max-width: 760px;
  margin: 24px 0 0;
  color: rgba(15, 23, 42, 0.62);
  font-size: 1.1rem;
  line-height: 1.95;
}

.highlight-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin-top: 34px;
}

.highlight-card {
  min-height: 148px;
  padding: 22px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 28px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(248, 250, 252, 0.72)),
    rgba(255, 255, 255, 0.72);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.75),
    0 18px 40px rgba(15, 23, 42, 0.06);
  transition: all 0.4s cubic-bezier(0.25, 0.8, 0.25, 1);
  backdrop-filter: blur(16px);
}

.highlight-card:hover {
  transform: translateY(-4px);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.84),
    0 26px 56px rgba(15, 23, 42, 0.1);
}

.highlight-card p {
  margin: 0;
  color: #0f172a;
  font-size: 1rem;
  font-weight: 700;
}

.highlight-card span {
  display: block;
  margin-top: 14px;
  color: rgba(15, 23, 42, 0.58);
  line-height: 1.8;
}

.panel {
  padding: 30px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 36px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.88), rgba(245, 247, 250, 0.74)),
    rgba(255, 255, 255, 0.76);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.8),
    0 24px 60px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(18px);
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 22px;
}

.metric-item {
  padding: 14px 12px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.68);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
  text-align: center;
}

.metric-item strong {
  display: block;
  color: #0f172a;
  font-size: 1.4rem;
  line-height: 1.1;
}

.metric-item span {
  display: block;
  margin-top: 6px;
  color: rgba(15, 23, 42, 0.5);
  font-size: 0.8rem;
  line-height: 1.45;
}

.note-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 14px;
}

.note-list li {
  position: relative;
  padding-left: 20px;
  color: rgba(15, 23, 42, 0.72);
  line-height: 1.85;
}

.note-list li::before {
  content: "";
  position: absolute;
  left: 0;
  top: 11px;
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: linear-gradient(135deg, #2563eb, #60a5fa);
}

@media (max-width: 980px) {
  .hero {
    grid-template-columns: 1fr;
  }

  .highlight-grid,
  .metric-grid {
    grid-template-columns: 1fr;
  }

  h1 {
    max-width: none;
  }
}
</style>
