/* eslint-disable no-return-await */
/* eslint-disable no-param-reassign */
/* eslint-disable import/no-cycle */
import { produce } from 'immer'
import { Ledfx } from '../../api/ledfx'
import type { IPresets } from './storeConfig'
import type { IStore } from '../useStore'

const storePresets = (set: any) => ({
  presets: {} as IPresets,
  getPresets: async (effectId: string) => {
    const resp = await Ledfx(`/api/effects/${effectId}/presets`)
    if (resp && resp.status === 'success') {
      delete resp.status
      set(
        produce((s: IStore) => {
          s.presets = resp as IPresets
        }),
        false,
        'gotPresets'
      )
    }
  },
  addPreset: async (effectId: string, name: string) =>
    await Ledfx(`/api/virtuals/${effectId}/presets`, 'POST', { name }),
  activatePreset: async (
    virtId: string,
    category: string,
    effectType: string,
    presetId: string
  ) =>
    await Ledfx(`/api/virtuals/${virtId}/presets`, 'PUT', {
      category,
      effect_id: effectType,
      preset_id: presetId
    }),
  deletePreset: async (effectId: string, presetId: string) =>
    await Ledfx(`/api/effects/${effectId}/presets`, 'DELETE', {
      data: {
        preset_id: presetId,
        category: 'user_presets'
      }
    })
})

export default storePresets
