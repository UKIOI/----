<script setup lang="ts">
const emit = defineEmits<{ move: [x: number, y: number]; aim: [x: number, y: number] }>()
</script>
<template><div class="mobile-controls"><button @pointerdown="emit('move', -1, 0)" @pointerup="emit('move', 0, 0)">◀</button><button @pointerdown="emit('move', 1, 0)" @pointerup="emit('move', 0, 0)">▶</button><button @pointerdown="emit('aim', 0, -1)" @pointerup="emit('aim', 0, 0)">▲</button></div></template>
