/* eslint-disable no-return-await */
/* eslint-disable no-param-reassign */
/* eslint-disable import/no-cycle */
import { produce } from 'immer'
import { Ledfx } from '../../api/ledfx'
import type { IStore } from '../useStore'

export type Segment = [
  device: string,
  start: number,
  end: number,
  reverse: boolean
]

export interface EffectConfig {
  background_brightness?: number
  background_color?: string
  beat_skip?: 'none' | 'odd' | 'even'
  blur?: number
  brightness?: number
  color?: string
  color_correction?: boolean
  color_step?: number
  decay?: number
  ease_method?: string
  flip?: boolean
  frequency_range?: string
  gradient?: string
  gradient_name?: string
  gradient_repeat?: number
  gradient_roll?: number
  invert_roll?: boolean
  mirror?: boolean
  mode?: string
  multiplier?: number
  skip_every?: number
  solid_color?: boolean
  advanced?: boolean
  beat_frames?: string
  flip_horizontal?: boolean
  flip_vertical?: boolean
  force_aspect?: boolean
  force_fit?: boolean
  gif_at?: string
  ping_pong?: boolean
  skip_frames?: string
  strech_hor?: number
  strech_ver?: number
  diag?: boolean
  diag2?: boolean
  dump?: boolean
  fake_beat?: boolean
  rotate?: number
  test?: string
  speed_x?: number
  size_x?: number
  pulse_period?: number
  pulse_ratio?: number
  flash_color?: string
  capture?: boolean
  cpu_secs?: number
  v_density?: number
  twist?: number
  radius?: number
  density?: number
  lower?: number
}

export interface Effect {
  config: EffectConfig
  name: string
  type: string
}

export interface Virtual {
  config: {
    center_offset: number
    frequency_max: number
    frequency_min: number
    icon_name: string
    mapping: string
    max_brightness: number
    name: string
    preview_only: boolean
    rows: number
    transition_mode: string
    transition_time: number
  }
  id: string
  is_device: string
  auto_generated: boolean
  segments: Segment[]
  pixel_count: number
  active: boolean
  effect: Effect
}

const storeVirtuals = (set: any) => ({
  virtuals: {} as Record<string, Virtual>,
  activeSegment: -1,
  setActiveSegment: (v: number) =>
    set(
      produce((state: IStore) => {
        state.activeSegment = v
      }),
      false,
      'api/setCurrentVirtual'
    ),
  currentVirtual: null as null | string,
  setCurrentVirtual: (v: null | string) =>
    set(
      produce((state: IStore) => {
        state.currentVirtual = v
      }),
      false,
      'api/setCurrentVirtual'
    ),
  getVirtuals: async () => {
    const resp = await Ledfx('/api/virtuals')
    if (resp) {
      set(
        produce((state: IStore) => {
          state.paused = resp.paused
        }),
        false,
        'api/gotPausedState'
      )
      if (resp && resp.virtuals) {
        set(
          produce((state: IStore) => {
            state.virtuals = resp.virtuals as Record<string, Virtual>
          }),
          false,
          'api/gotVirtuals'
        )
      }
    }
  },
  addVirtual: async (config: any) =>
    await Ledfx('/api/virtuals', 'POST', config),
  updateVirtual: async (virtId: string, active: boolean) =>
    await Ledfx(`/api/virtuals/${virtId}`, 'PUT', { active }),
  deleteVirtual: async (virtId: string) =>
    await Ledfx(`/api/virtuals/${virtId}`, 'DELETE'),
  clearEffect: async (virtId: string) =>
    await Ledfx(`/api/virtuals/${virtId}/effects`, 'DELETE'),
  setEffect: async (
    virtId: string,
    type: string,
    config: any,
    active: boolean
  ) => {
    const resp = await Ledfx(`/api/virtuals/${virtId}/effects`, 'POST', {
      type,
      config,
      active
    })

    if (resp && resp.effect) {
      set(
        produce((state: IStore) => {
          state.virtuals[virtId].effect = {
            type: (resp.effect as Effect).type,
            name: (resp.effect as Effect).name,
            config: (resp.effect as Effect).config
          }
        }),
        false,
        'api/setEffect'
      )
    }
  },
  updateEffect: async (
    virtId: string,
    type: string,
    config: EffectConfig,
    active: boolean
  ) => {
    const resp = await Ledfx(`/api/virtuals/${virtId}/effects`, 'PUT', {
      type,
      config,
      active
    })
    if (resp && resp.status && resp.status === 'success') {
      if (resp && resp.effect) {
        set(
          produce((state: IStore) => {
            state.virtuals[virtId].effect = {
              type: (resp.effect as Effect).type,
              name: (resp.effect as Effect).name,
              config: (resp.effect as Effect).config
            }
          }),
          false,
          'api/updateEffect'
        )
      }
    }
  },
  copyTo: async (virtId: string, target: string[]) => {
    const resp = await Ledfx(`/api/virtuals_tools/${virtId}`, 'PUT', {
      tool: 'copy',
      target
    })
    if (resp && resp.status && resp.status === 'success') {
      return true
    }
    return false
  },
  updateSegments: async (virtId: string, segments: Segment[]) => {
    const resp = await Ledfx(`/api/virtuals/${virtId}`, 'POST', {
      segments: [...segments]
    })
    if (resp && resp.status && resp.status === 'success') {
      if (resp && resp.effect) {
        set(
          produce((state: IStore) => {
            state.virtuals[virtId].effect = {
              type: (resp.effect as Effect).type,
              name: (resp.effect as Effect).name,
              config: (resp.effect as Effect).config
            }
          }),
          false,
          'api/updateVirtualsSegments'
        )
      }
    }
  },
  highlightSegment: async (
    virtId: string,
    device: string,
    start: number,
    stop: number,
    flip: boolean
  ) => {
    const resp = await Ledfx(`/api/virtuals_tools/${virtId}`, 'PUT', {
      tool: 'highlight',
      device,
      start,
      stop,
      flip
    })
    if (resp && resp.status && resp.status === 'success') {
      return true
    }
    return false
  },
  highlightOffSegment: async (virtId: string) => {
    const resp = await Ledfx(`/api/virtuals_tools/${virtId}`, 'PUT', {
      tool: 'highlight',
      state: false
    })
    if (resp && resp.status && resp.status === 'success') {
      return true
    }
    return false
  },
  calibrationMode: async (virtId: string, mode: 'on' | 'off') => {
    const resp = await Ledfx(`/api/virtuals_tools/${virtId}`, 'PUT', {
      tool: 'calibration',
      mode
    })
    if (resp && resp.status && resp.status === 'success') {
      return true
    }
    return false
  },
  oneShotAll: async (
    color: string,
    ramp: number,
    hold: number,
    fade: number
  ) => {
    const resp = await Ledfx('/api/virtuals_tools', 'PUT', {
      tool: 'oneshot',
      color,
      ramp,
      hold,
      fade
    })
    if (resp && resp.status && resp.status === 'success') {
      return true
    }
    return false
  },
  oneShot: async (
    virtId: string,
    color: string,
    ramp: number,
    hold: number,
    fade: number
  ) => {
    const resp = await Ledfx(`/api/virtuals_tools/${virtId}`, 'PUT', {
      tool: 'oneshot',
      color,
      ramp,
      hold,
      fade
    })
    if (resp && resp.status && resp.status === 'success') {
      return true
    }
    return false
  }
})

export default storeVirtuals
