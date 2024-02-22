/* eslint-disable no-return-await */
/* eslint-disable no-param-reassign */
/* eslint-disable import/no-cycle */
import { produce } from 'immer'
import { Ledfx } from '../../api/ledfx'
import type { IStore, IOpenRgbDevice } from '../useStore'
import type { IDevice } from './storeConfig'

const storeDevices = (set: any) => ({
  devices: {} as Record<string, IDevice>,
  openRgbDevices: [] as IOpenRgbDevice[],
  launchpadDevice: '' as string,
  getDevices: async () => {
    const resp = await Ledfx('/api/devices')
    if (resp && resp.devices) {
      set(
        produce((state: IStore) => {
          state.devices = resp.devices as Record<string, IDevice>
        }),
        false,
        'api/gotDevices'
      )
    }
  },
  getDevice: async (deviceId: string) => {
    const resp = await Ledfx(`/api/devices/${deviceId}`)
    if (resp && resp.data) {
      return {
        key: deviceId,
        id: deviceId,
        name: resp.data.name,
        config: resp.data,
        virtuals: resp.data.virtuals,
        active_virtuals: resp.data.active_virtuals
      }
    }
    return {}
  },
  addDevice: async (config: any) => await Ledfx('/api/devices', 'POST', config),
  activateDevice: async (deviceId: string) => {
    const resp = await Ledfx(`/api/devices/${deviceId}`, 'POST', {})
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
            state.virtuals = resp.virtuals
          }),
          false,
          'api/gotVirtuals'
        )
      }
    }
  },
  updateDevice: async (deviceId: string, config: any) =>
    await Ledfx(`/api/devices/${deviceId}`, 'PUT', config)
})

export default storeDevices
