/* eslint-disable @typescript-eslint/indent */
/* eslint-disable no-return-await */
/* eslint-disable no-param-reassign */
/* eslint-disable import/no-cycle */
import { produce } from 'immer'
import { Ledfx } from '../../api/ledfx'
import type { IStore } from '../useStore'

const storeScenes = (set: any) => ({
  scenes: {} as Record<string, Record<string, any>>,
  mostUsedScenes: {} as any,
  recentScenes: [] as string[],
  count: {} as any,
  scenePL: [] as any,
  scenePLplay: false,
  scenePLrepeat: false,
  scenePLactiveIndex: -1,
  scenePLinterval: 2,
  toggleScenePLplay: () => {
    set(
      produce((s: IStore) => {
        s.scenePLplay = !s.scenePLplay
      }),
      false,
      'toggleScenePLplay'
    )
  },
  toggleScenePLrepeat: () => {
    set(
      produce((s: IStore) => {
        s.scenePLrepeat = !s.scenePLrepeat
      }),
      false,
      'toggleScenePLrepeat'
    )
  },
  setScenePLinterval: (seconds: number) => {
    set(
      produce((s: IStore) => {
        s.scenePLinterval = seconds
      }),
      false,
      'setScenePLinterval'
    )
  },
  setMostUsedScenes: (key: string, count: number) => {
    set(
      produce((s: IStore) => {
        s.mostUsedScenes[key] = {
          ...s.scenes[key],
          used: count
        }
      }),
      false,
      'setMostUsedScenes'
    )
  },
  setScenePL: (scenes: string[]) => {
    set(
      produce((s: IStore) => {
        s.scenePL = scenes
      }),
      false,
      'setScenePLactiveIndex'
    )
  },
  setScenePLactiveIndex: (index: number) => {
    set(
      produce((s: IStore) => {
        s.scenePLactiveIndex = index
      }),
      false,
      'setScenePLactiveIndex'
    )
  },
  addScene2PL: (sceneId: string) => {
    set(
      produce((s: IStore) => {
        s.scenePL = [...s.scenePL, sceneId]
      }),
      false,
      'addScene2PL'
    )
  },
  removeScene2PL: (id: number) => {
    set(
      produce((s: IStore) => {
        s.scenePL = s.scenePL.filter((p: string, i: number) => i !== id)
      }),
      false,
      'removeScene2PL'
    )
  },
  getScenes: async () => {
    const resp = await Ledfx('/api/scenes')
    if (resp && resp.scenes) {
      set(
        produce((s: IStore) => {
          s.scenes = resp.scenes
        }),
        false,
        'gotScenes'
      )
      return resp.scenes
    }
    return null
  },
  addScene: async (
    name: string,
    scene_image?: string,
    scene_tags?: string,
    scene_puturl?: string,
    scene_payload?: string,
    scene_midiactivate?: string,
    virtuals?: Record<string, any>
  ) =>
    virtuals
      ? await Ledfx('/api/scenes', 'POST', {
          name,
          scene_image,
          scene_tags,
          scene_puturl,
          scene_payload,
          scene_midiactivate,
          virtuals
        })
      : await Ledfx('/api/scenes', 'POST', {
          name,
          scene_image,
          scene_tags,
          scene_puturl,
          scene_payload,
          scene_midiactivate
        }),
  activateScene: async (id: string) => {
    set(
      produce((s: IStore) => {
        s.recentScenes = s.recentScenes
          ? s.recentScenes.indexOf(id) > -1
            ? [id, ...s.recentScenes.filter((t: any) => t !== id)]
            : [id, ...s.recentScenes].slice(0, 5)
          : [id]
      }),
      false,
      'setScenes'
    )
    set(
      produce((s: IStore) => {
        s.count[id] = (s.count[id] || 0) + 1
      }),
      false,
      'setScenes'
    )
    return await Ledfx('/api/scenes', 'PUT', {
      id,
      action: 'activate'
    })
  },
  activateSceneIn: async (id: string, ms: number) =>
    await Ledfx('/api/scenes', 'PUT', {
      id,
      action: 'activate_in',
      ms
    }),
  deleteScene: async (name: string) =>
    await Ledfx('/api/scenes', 'DELETE', { data: { id: name } }),

  captivateScene: async (scene_puturl: string, scene_payload: string) =>
    await Ledfx(scene_puturl, 'PUT', JSON.parse(scene_payload))
})

export default storeScenes
