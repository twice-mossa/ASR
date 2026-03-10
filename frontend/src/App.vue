<template>
  <main class="page-shell">
    <section class="hero">
      <p class="eyebrow">ASR Meeting Assistant</p>
      <h1>智能会议助手</h1>
      <p class="intro">
        上传会议录音，自动转写内容，生成纪要，提取关键词，并为后续搜索与回放提供时间戳基础。
      </p>
    </section>

    <section class="card-grid">
      <div class="card">
        <h2>当前开发重点</h2>
        <ul>
          <li>接入 faster-whisper 完成语音转写</li>
          <li>调用 MiniMax 生成会议纪要和关键词</li>
          <li>实现关键词检索和片段回放</li>
        </ul>
      </div>

      <div class="card">
        <h2>三人协作建议</h2>
        <ul>
          <li>A 同学：后端接口与模型接入</li>
          <li>B 同学：前端页面与交互</li>
          <li>C 同学：数据处理、测试和文档</li>
        </ul>
      </div>
    </section>
  </main>
</template>

<style scoped>
:global(body) {
  margin: 0;
  font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
  background:
    radial-gradient(circle at top left, #ffd9a8 0%, transparent 28%),
    radial-gradient(circle at right, #c6f1e7 0%, transparent 24%),
    linear-gradient(135deg, #f7f1e8 0%, #eef6ff 100%);
  color: #1d2a36;
}

:global(*) {
  box-sizing: border-box;
}

.page-shell {
  min-height: 100vh;
  padding: 56px 20px;
}

.hero {
  max-width: 860px;
  margin: 0 auto 28px;
}

.eyebrow {
  margin: 0 0 12px;
  color: #915f00;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

h1 {
  margin: 0;
  font-size: clamp(2.4rem, 4vw, 4.4rem);
}

.intro {
  max-width: 680px;
  font-size: 1.05rem;
  line-height: 1.75;
}

.card-grid {
  max-width: 860px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 20px;
}

.card {
  padding: 24px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.78);
  box-shadow: 0 18px 60px rgba(48, 60, 80, 0.12);
  backdrop-filter: blur(8px);
}

.card h2 {
  margin-top: 0;
}

.card ul {
  padding-left: 20px;
  line-height: 1.9;
}
</style>
