export type Mode = 'classic' | 'items' | 'pure' | 'profession'
export type Role = 'tank' | 'mage' | 'sniper' | 'necromancer' | 'weaponmaster' | 'paladin'
export interface Player { id: string; name: string; x: number; y: number; hp: number; max_hp: number; score: number; color: string; role: Role | null; ready: boolean }
export interface GameState { type: 'state'; players: Player[]; bullets: Array<{x:number;y:number;color:string}>; lasers: Array<{x1:number;y1:number;x2:number;y2:number;color:string}>; pickups: Array<{x:number;y:number;kind:string}>; destroyed: Array<[number, number]> }
export interface Welcome { type: 'welcome'; id: string; room: string; mode: Mode; edition: string; width: number; height: number; obstacles: Array<{id:number;x:number;y:number;w:number;h:number;active:boolean}> }
