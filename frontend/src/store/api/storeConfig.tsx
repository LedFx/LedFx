/* eslint-disable no-return-await */
/* eslint-disable no-param-reassign */
/* eslint-disable import/no-cycle */
import { produce } from 'immer'
import { Ledfx } from '../../api/ledfx'
import type { IStore } from '../useStore'
import { EffectConfig } from './storeVirtuals'

export interface Schema {
  type: string
  title: string
  properties: any
  required: string[]
  order: string[]
}

export interface Intergration {
  active: boolean
  config: Record<string, any>
  data: Record<string, any>
  id: string
  type: string
  status?: number
  beta?: boolean
}

export interface IPreset {
  name: string
  config: EffectConfig
}
export interface IPresets {
  effect: string
  ledfx_presets: Record<string, IPreset>
  user_presets: Record<string, IPreset>
}

export interface IDevice {
  config: Record<string, any>
  id: string
  type: string
  online?: boolean
  virtuals?: string[]
  active_virtuals?: string[]
}

export interface ISystemConfig {
  integrations: undefined
  user_gradients: Record<string, string>
  global_brightness: number
  visualisation_fps: number
  transmission_mode?: 'compressed' | 'uncompressed'
  dev_mode: boolean
  // ledfx_presets: Record<string, Record<string, IPreset>>
  ledfx_presets: undefined
  audio: {
    audio_device: number
    delay_ms: number
    fft_size: number
    mic_rate: number
    min_volume: number
    sample_rate: number
    pitch_method: string
    pitch_tolerance: number
    onset_method: string
  }
  user_colors: Record<string, string>
  devices: undefined
  create_segments: boolean
  wled_preferences: Record<string, any>
  melbanks: {
    max_frequencies: number[]
    min_frequency: number
  }
  global_transitions: boolean
  virtuals: undefined
  host: string
  visualisation_maxlen: number
  port_s: number
  user_presets: Record<string, Record<string, IPreset>>
  port: number
  configuration_version: string
  scenes: undefined
  scan_on_startup: boolean
}

const storeConfig = (set: any) => ({
  schemas: {} as any,
  getSchemas: async () => {
    const resp = await Ledfx('/api/schema')
    if (resp) {
      set(
        produce((s: IStore) => {
          s.schemas = resp
        }),
        false,
        'gotSchemas'
      )
    }
  },

  config: {} as ISystemConfig,
  getSystemConfig: async () => {
    const resp = await Ledfx('/api/config')
    if (resp && resp.host) {
      set(
        produce((state: IStore) => {
          state.config = {
            ...resp,
            ...{
              ledfx_presets: undefined,
              devices: undefined,
              virtuals: undefined,
              integrations: undefined,
              scenes: undefined
            }
          } as ISystemConfig
        }),
        false,
        'api/gotSystemConfig'
      )
    } else {
      set(
        produce((state: IStore) => {
          state.dialogs.nohost.open = true
        }),
        false,
        'api/failedSystemConfig'
      )
    }
  },
  getFullConfig: async () => {
    const resp = await Ledfx('/api/config')
    if (resp && resp.host) {
      return { ...resp, ...{ ledfx_presets: undefined } }
    }
    return set(
      produce((state: IStore) => {
        state.dialogs.nohost.open = true
      }),
      false,
      'api/getFullConfig'
    )
  },
  getLedFxPresets: async () => {
    const resp = await Ledfx('/api/config')
    if (resp && resp.host) {
      return resp.ledfx_presets
    }
    return set(
      produce((state: IStore) => {
        state.dialogs.nohost.open = true
      }),
      false,
      'api/getLedFxPresets'
    )
  },
  getUserPresets: async () => {
    const resp = await Ledfx('/api/config')
    if (resp && resp.host) {
      set(
        produce((state: IStore) => {
          state.config.user_presets = resp.user_presets
        }),
        false,
        'api/getUserPresets'
      )
      return resp.user_presets
    }
    return set(
      produce((state: IStore) => {
        state.dialogs.nohost.open = true
      }),
      false,
      'api/getUserPresets'
    )
  },
  setSystemConfig: async (config: any) =>
    await Ledfx('/api/config', 'PUT', config),
  deleteSystemConfig: async () => await Ledfx('/api/config', 'DELETE'),
  importSystemConfig: async (config: any) =>
    await Ledfx('/api/config', 'POST', config)
})

export default storeConfig
