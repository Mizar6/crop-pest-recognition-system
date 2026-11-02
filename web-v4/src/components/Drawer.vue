<script setup>
defineProps({
  show: Boolean,
  title: String,
  width: { type: String, default: '560px' }
})
const emit = defineEmits(['close'])
</script>

<template>
  <teleport to="body">
    <transition name="slide">
      <div v-if="show" class="mask" @click.self="emit('close')">
        <div class="drawer" :style="{ width, maxWidth: '92vw' }">
          <div class="head">
            <b>{{ title }}</b>
            <button class="btn ghost sm" @click="emit('close')">✕</button>
          </div>
          <div class="body">
            <slot />
          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<style scoped>
.mask {
  position: fixed; inset: 0; background: rgba(15, 30, 18, .4);
  backdrop-filter: blur(2px); z-index: 1000;
  display: flex; justify-content: flex-end;
}
.drawer {
  background: #fff; height: 100%; display: flex; flex-direction: column;
  box-shadow: -12px 0 40px rgba(15, 30, 18, .18);
}
.head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 22px; border-bottom: 1px solid var(--line); font-size: 15.5px;
}
.body { padding: 20px 22px 40px; overflow-y: auto; flex: 1; }
.slide-enter-active, .slide-leave-active { transition: all .22s ease; }
.slide-enter-from, .slide-leave-to { opacity: 0; }
.slide-enter-from .drawer, .slide-leave-to .drawer { transform: translateX(40px); }
</style>
