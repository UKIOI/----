<script setup lang="ts">
import type { Mode } from '../types/protocol'
defineProps<{ name: string; room: string; mode: Mode; offline: boolean }>()
const emit = defineEmits<{ join: []; 'update:name': [value: string]; 'update:room': [value: string]; 'update:mode': [value: Mode] }>()
</script>
<template>
  <section class="join-menu">
    <p class="eyebrow">NEON BRAWL / ONLINE ARENA</p><h1>霓虹乱斗</h1><p class="tagline">把策略、走位和一点点混乱带进同一片霓虹战场。</p>
    <label>昵称<input :value="name" maxlength="12" @input="emit('update:name', ($event.target as HTMLInputElement).value)" /></label>
    <label>房间号<input :value="room" maxlength="10" @input="emit('update:room', ($event.target as HTMLInputElement).value)" /></label>
    <label>玩法<select :value="mode" @change="emit('update:mode', ($event.target as HTMLSelectElement).value as Mode)"><option value="classic">经典模式</option><option value="items">多道具模式</option><option value="pure">纯净模式</option><option value="profession">职业模式</option></select></label>
    <button class="primary" @click="emit('join')">进入战场</button>
    <small>{{ offline ? '离线模式：连接仅限本机' : '支持局域网、互联网与 WSS' }}</small>
  </section>
</template>
