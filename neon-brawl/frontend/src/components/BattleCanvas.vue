<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import type { GameState, Welcome } from '../types/protocol'
const props = defineProps<{ state: GameState | null; world: Welcome | null; playerId: string | null }>()
const canvas = ref<HTMLCanvasElement>()
let frame = 0
function draw() {
  const element = canvas.value; const context = element?.getContext('2d'); if (!element || !context) return
  const world = props.world; const state = props.state; const scale = Math.min(innerWidth / (world?.width || 1600), innerHeight / (world?.height || 900))
  element.width = innerWidth * devicePixelRatio; element.height = innerHeight * devicePixelRatio; context.setTransform(devicePixelRatio * scale, 0, 0, devicePixelRatio * scale, 0, 0)
  context.fillStyle = '#080c18'; context.fillRect(0, 0, (world?.width || 1600), (world?.height || 900))
  context.strokeStyle = 'rgba(76, 232, 255, .12)'; context.lineWidth = 2
  for (const obstacle of world?.obstacles || []) { context.fillStyle = obstacle.active ? '#17253c' : '#0d1423'; context.fillRect(obstacle.x, obstacle.y, obstacle.w, obstacle.h); context.strokeRect(obstacle.x, obstacle.y, obstacle.w, obstacle.h) }
  for (const bullet of state?.bullets || []) { context.fillStyle = bullet.color || '#ffe66d'; context.beginPath(); context.arc(bullet.x, bullet.y, 6, 0, Math.PI * 2); context.fill() }
  for (const laser of state?.lasers || []) { context.strokeStyle = laser.color || '#ff5dd6'; context.lineWidth = 5; context.beginPath(); context.moveTo(laser.x1, laser.y1); context.lineTo(laser.x2, laser.y2); context.stroke() }
  for (const player of state?.players || []) { context.fillStyle = player.color; context.beginPath(); context.arc(player.x, player.y, 25, 0, Math.PI * 2); context.fill(); context.strokeStyle = player.id === props.playerId ? '#fff' : '#101827'; context.lineWidth = 3; context.stroke(); context.fillStyle = '#fff'; context.font = '600 16px Chakra Petch'; context.textAlign = 'center'; context.fillText(player.name, player.x, player.y - 34); context.fillStyle = '#23101d'; context.fillRect(player.x - 25, player.y + 31, 50, 5); context.fillStyle = '#70f6a7'; context.fillRect(player.x - 25, player.y + 31, 50 * Math.max(0, player.hp / player.max_hp), 5) }
  frame = requestAnimationFrame(draw)
}
onMounted(() => { frame = requestAnimationFrame(draw); addEventListener('resize', draw) })
onUnmounted(() => { cancelAnimationFrame(frame); removeEventListener('resize', draw) })
watch(() => props.state, draw)
</script>
<template><canvas ref="canvas" class="battle-canvas" aria-label="战斗场景" /></template>
