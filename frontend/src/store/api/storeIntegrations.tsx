/* eslint-disable no-return-await */
/* eslint-disable no-param-reassign */
/* eslint-disable import/no-cycle */
import { produce } from 'immer'
import { Ledfx } from '../../api/ledfx'
import type { IStore } from '../useStore'
import type { Intergration } from './storeConfig'

const storeIntegrations = (set: any) => ({
  integrations: {} as Record<string, Intergration>,
  getIntegrations: async () => {
    const resp = await Ledfx('/api/integrations')
    if (resp && resp.integrations) {
      // console.log(resp.integrations);
      set(
        produce((s: IStore) => {
          s.integrations = resp.integrations as Record<string, Intergration>
        }),
        false,
        'gotIntegrations'
      )
    }
  },
  addIntegration: async (config: Record<string, any>) =>
    await Ledfx('/api/integrations', 'POST', config),
  updateIntegration: async (config: Record<string, any>) =>
    await Ledfx('/api/integrations', 'POST', config),
  toggleIntegration: async (config: Record<string, any>) =>
    await Ledfx('/api/integrations', 'PUT', config),
  deleteIntegration: async (id: string) =>
    await Ledfx('/api/integrations', 'DELETE', { data: { id } })
})

export default storeIntegrations
