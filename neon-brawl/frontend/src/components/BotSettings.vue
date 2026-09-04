<script setup lang="ts">
defineProps<{ visible: boolean; count: number; difficulty: string }>(); const emit = defineEmits<{ configure: [count: number, difficulty: string] }>()
</script>
<template><div v-if="visible" class="bot-settings"><label>人机数量 <input type="number" min="0" max="11" :value="count" @change="emit('configure', Number(($event.target as HTMLInputElement).value), difficulty)" /></label><select :value="difficulty" @change="emit('configure', count, ($event.target as HTMLSelectElement).value)"><option value="easy">简单</option><option value="normal">普通</option><option value="hard">困难</option></select></div></template>
