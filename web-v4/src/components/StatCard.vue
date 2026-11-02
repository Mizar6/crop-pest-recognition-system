<script setup>
defineProps({
  label: String,
  value: [String, Number],
  sub: String,
  icon: String,
  tone: { type: String, default: 'green' }
})
</script>

<template>
  <div class="stat-card">
    <div class="val">{{ value }}</div>
    <div class="label">{{ label }}</div>
    <div class="sub" v-if="sub">{{ sub }}</div>
  </div>
</template>

<style scoped>
.stat-card {
  display: flex; flex-direction: column; gap: 3px;
  padding: 20px 22px;
  background: var(--paper-2);
  border-right: 1px solid var(--rule-soft);
}
.stat-card:last-child { border-right: 0; }
.val {
  font-family: "Noto Serif SC", "Songti SC", serif;
  font-size: 34px; font-weight: 700; line-height: 1;
  color: var(--ink); font-variant-numeric: tabular-nums;
}
.label {
  font-family: var(--mono); font-size: 9.5px; letter-spacing: .18em;
  text-transform: uppercase; color: var(--muted); margin-top: 6px;
}
.sub { font-size: 11.5px; color: var(--muted); margin-top: 2px; }
</style>