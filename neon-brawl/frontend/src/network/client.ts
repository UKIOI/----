import type { Mode, Role } from '../types/protocol'

export function websocketUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL as string | undefined
  if (configured) return configured.replace(/^http/, 'ws') + '/ws'
  return `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`
}
export function joinPayload(name: string, room: string, mode: Mode) { return { type: 'join', name, room, mode } }
export function inputPayload(seq: number, moveX: number, moveY: number, angle: number, shoot: boolean) { return { type: 'input', seq, move_x: moveX, move_y: moveY, angle, shoot } }
export function rolePayload(role: Role) { return { type: 'role', role } }
