<script setup lang="ts">
defineProps<{ status: string; playerCount: number; room: string; edition: string }>()
</script>
<template><header class="hud"><strong>霓虹乱斗</strong><span>{{ room }} · {{ playerCount }} 人在线</span><span class="status">{{ status }}</span><span class="edition">{{ edition }}</span></header></template>
