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
  margin: 0 auto 28px;
  display: grid;
  grid-template-columns: minmax(0, 1.34fr) minmax(320px, 0.86fr);
  gap: 28px;
  align-items: end;
}

.copy {
  position: relative;
  padding: 18px 0 10px;
}

.copy::before {
  content: "";
  position: absolute;
  left: -28px;
  top: -12px;
  width: 240px;
  height: 240px;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(249, 115, 22, 0.16) 0%, rgba(249, 115, 22, 0) 72%);
  pointer-events: none;
}

.eyebrow-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.eyebrow,
.panel-label,
.eyebrow-badge {
  margin: 0 0 16px;
  color: #64748b;
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.eyebrow-badge {
  display: inline-flex;
  align-items: center;
  padding: 8px 12px;
  margin-bottom: 16px;
  border: 1px solid rgba(37, 99, 235, 0.14);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  color: #2563eb;
  letter-spacing: 0.12em;
}

h1 {
  margin: 0;
  max-width: 9ch;
  font-family: "Calistoga", "Iowan Old Style", "Palatino Linotype", serif;
  font-size: clamp(3.4rem, 8vw, 6.4rem);
  line-height: 0.96;
  letter-spacing: -0.04em;
  text-wrap: balance;
}

.intro {
  max-width: 760px;
  margin: 24px 0 0;
  color: #516275;
  font-size: 1.08rem;
  line-height: 1.9;
}

.highlight-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-top: 30px;
}

.highlight-card {
  min-height: 136px;
  padding: 20px;
  border: 1px solid rgba(37, 99, 235, 0.08);
  border-radius: 26px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.88), rgba(241, 245, 249, 0.72)),
    rgba(255, 255, 255, 0.7);
  box-shadow: 0 18px 40px rgba(30, 41, 59, 0.08);
  transition: transform 220ms ease, box-shadow 220ms ease;
}

.highlight-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 24px 48px rgba(30, 41, 59, 0.12);
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
  color: #64748b;
  line-height: 1.75;
}

.panel {
  padding: 28px;
  border: 1px solid rgba(37, 99, 235, 0.1);
  border-radius: 34px;
  background:
    linear-gradient(160deg, rgba(255, 255, 255, 0.92), rgba(239, 246, 255, 0.78)),
    rgba(255, 255, 255, 0.72);
  box-shadow: 0 24px 60px rgba(30, 41, 59, 0.12);
  backdrop-filter: blur(16px);
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 22px;
}

.metric-item {
  padding: 14px 12px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.74);
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
  color: #64748b;
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
  color: #334155;
  line-height: 1.8;
}

.note-list li::before {
  content: "";
  position: absolute;
  left: 0;
  top: 11px;
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: linear-gradient(135deg, #2563eb, #f97316);
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
