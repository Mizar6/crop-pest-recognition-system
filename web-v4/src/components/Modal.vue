<script setup>
defineProps({
  show: Boolean,
  title: String,
  width: { type: String, default: '640px' }
})
const emit = defineEmits(['close'])
</script>

<template>
  <teleport to="body">
    <transition name="pop">
      <div v-if="show" class="mask" @click.self="emit('close')">
        <div class="modal card" :style="{ width, maxWidth: '94vw' }">
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
  position: fixed; inset: 0; background: rgba(15, 30, 18, .45);
  backdrop-filter: blur(3px); z-index: 1000;
  display: flex; align-items: center; justify-content: center; padding: 24px;
}
.modal { max-height: 88vh; display: flex; flex-direction: column; overflow: hidden; }
.head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 15px 20px; border-bottom: 1px solid var(--line); font-size: 15px;
}
.body { padding: 20px; overflow-y: auto; }
</style>
