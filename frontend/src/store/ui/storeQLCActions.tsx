/* eslint-disable import/no-cycle */
/* eslint-disable no-param-reassign */

import { produce } from 'immer'
import { Ledfx } from '../../api/ledfx'
import type { IStore } from '../useStore'

const storeQLCActions = (set: any) => ({
  setQLCEmbedUrl: (url: string) =>
    set(
      produce((state: IStore) => {
        state.qlc.QLCEmbedUrl = url
      }),
      false,
      'qlc/setQLCEmbedUrl'
    ),
  setQLCPos: (pos: any) =>
    set(
      produce((state: IStore) => {
        state.qlc.QLCPos = pos
      }),
      false,
      'qlc/setQLCPos'
    ),
  setQLCData: (type: string, data: any) =>
    set(
      produce((state: IStore) => {
        state.qlc.QLCData[type] = data
      }),
      false,
      'qlc/setQLCData'
    ),
  getQLCTriggers: async () => {
    const resp = await Ledfx('/api/integrations', set, 'GET')
    // const res = await resp.json()
    if (resp) {
      set(
        produce((state: IStore) => {
          state.qlc.qlc = resp.qlc
        }),
        false,
        'qlc/getTriggers'
      )
    }
  },
  setQLCActTriggers: async (ids: string[]) => {
    set(
      produce((state: IStore) => {
        state.qlc.QLCActTriggers = ids
      }),
      false,
      'qlc/setTriggers'
    )
  },
  removeQLCActTriggers: async (id: string) => {
    set(
      produce((state: IStore) => {
        state.qlc.QLCActTriggers = state.qlc.QLCActTriggers.filter(
          (f: any) => f.id !== id
        )
      }),
      false,
      'qlc/delTriggers'
    )
  },
  addToQLCTriggerList: async (newTrigger: any, type: string) => {
    switch (type) {
      case 'create':
        set(
          produce((state: IStore) => {
            state.qlc.qlcTriggersList = [...newTrigger]
          }),
          false,
          'qlc/addToTriggerList'
        )
        break
      case 'update':
        set(
          produce((state: IStore) => {
            state.qlc.qlcTriggersList = [
              // ...state.addToQLCTriggerList, // @mattallmighty check this
              newTrigger
            ]
          }),
          false,
          'qlc/addToTriggerList'
        )
        break
      default:
    }
  },
  getQLCWidgets: async () => {
    const resp = await Ledfx('/api/integrations/qlc/qlc')
    // const res = await resp.json()
    if (resp) {
      set(
        produce((state: IStore) => {
          state.qlc.qlcWidgets = resp
        }),
        false,
        'qlc/getWidgets'
      )
    }
  },
  addQLCSongTrigger: async ({ event_type, event_filter, qlc_payload }: any) => {
    await Ledfx('/api/integrations/qlc/qlc', 'POST', {
      event_type,
      event_filter,
      qlc_payload
    })
  },
  toggleQLCTrigger: (QLCId: string, config: any) =>
    Ledfx(`/api/integrations/qlc/${QLCId}`, 'PUT', config),
  deleteQLCTrigger: async (config: any) => {
    await Ledfx('/api/integrations/qlc/qlc', 'DELETE', config)
    // set(state=>state.getIntegrations())
  }
})

export default storeQLCActions
