<script setup lang="ts">
import type { Role } from '../types/protocol'
defineProps<{ visible: boolean }>(); const emit = defineEmits<{ select: [role: Role] }>()
const roles: Array<[Role, string]> = [['tank', '坦克'], ['mage', '法师'], ['sniper', '狙击手'], ['necromancer', '死灵法师'], ['weaponmaster', '武器大师'], ['paladin', '圣骑士']]
</script>
<template><div v-if="visible" class="role-selector"><p>选择职业进入战场</p><button v-for="role in roles" :key="role[0]" @click="emit('select', role[0])">{{ role[1] }}</button></div></template>
