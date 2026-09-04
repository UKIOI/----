<script setup lang="ts">
import { ref } from 'vue'
defineProps<{ messages: Array<{ name: string; message: string; color: string }> }>()
const emit = defineEmits<{ send: [message: string] }>(); const draft = ref('')
function submit() { const message = draft.value.trim(); if (message) emit('send', message.slice(0, 120)); draft.value = '' }
</script>
<template><aside class="chat-panel"><h2>房间聊天</h2><div class="chat-messages"><p v-for="(item, index) in messages" :key="index"><b :style="{ color: item.color }">{{ item.name }}：</b>{{ item.message }}</p></div><form @submit.prevent="submit"><input v-model="draft" maxlength="120" placeholder="说点什么" /><button aria-label="发送">发送</button></form></aside></template>
