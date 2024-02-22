/* eslint-disable no-param-reassign */
import { produce } from 'immer'
import isElectron from 'is-electron'
import type { IStore } from '../useStore'

const storeGeneral = (set: any) => ({
  host: isElectron()
    ? 'http://localhost:8888'
    : window.location.href.split('#')[0],
  setHost: (host: any) => {
    window.localStorage.setItem('ledfx-host', host.title ? host.title : host)
    return set(
      produce((state: IStore) => {
        state.host = host
      }),
      false,
      'general/host'
    )
  },
  coreStatus: {} as Record<string, string>,
  setCoreStatus: (status: Record<string, string>) =>
    set(
      produce((state: IStore) => {
        state.coreStatus = status
      }),
      false,
      'general/setCoreStatus'
    ),
  coreParams: {} as Record<string, string[]>,
  setCoreParams: (params: Record<string, string[]>) =>
    set(
      produce((state: IStore) => {
        state.coreParams = params
      }),
      false,
      'general/setCoreParams'
    ),
  platform: 'yz',
  setPlatform: (platform: string) =>
    set(
      produce((state: IStore) => {
        state.platform = platform
      }),
      false,
      'general/setPlatform'
    ),
  protoCall: '',
  setProtoCall: (msg: string) =>
    set(
      produce((state: IStore) => {
        state.protoCall = msg
      }),
      false,
      'general/setPlatform'
    ),
  disconnected: false,
  setDisconnected: (dis: boolean) =>
    set(
      produce((state: IStore) => {
        state.disconnected = dis
      }),
      false,
      'general/setStreamingToDevices'
    ),
  streamingToDevices: [] as string[],
  setStreamingToDevices: (devices: any) => {
    set(
      produce((state: IStore) => {
        state.streamingToDevices = devices
      }),
      false,
      'general/setStreamingToDevices'
    )
  },
  streaming: false,
  setStreaming: (streaming: boolean) => {
    set(
      produce((state: IStore) => {
        state.streaming = streaming
      }),
      false,
      'general/setStreaming'
    )
  },
  // graphs: !!isElectron(),
  showActiveDevicesFirst: true,
  setShowActiveDevicesFirst: (val: boolean) => {
    set(
      produce((state: IStore) => {
        state.showActiveDevicesFirst = val
      }),
      false,
      'general/setShowActiveDevicesFirst'
    )
  },
  graphs: true,
  toggleGraphs: () => {
    set(
      produce((state: IStore) => {
        state.graphs = !state.graphs
      }),
      false,
      'general/toggleGraphs'
    )
  },
  graphsMulti: false,
  toggleGraphsMulti: () => {
    set(
      produce((state: IStore) => {
        state.graphsMulti = !state.graphsMulti
      }),
      false,
      'general/toggleGraphsMulti'
    )
  },
  showMatrix: false,
  toggleShowMatrix: () => {
    set(
      produce((state: IStore) => {
        state.showMatrix = !state.showMatrix
      }),
      false,
      'general/toggleShowMatrix'
    )
  },

  pixelGraphs: [] as string[],
  setPixelGraphs: (virtuals: string[]): void =>
    set(
      produce((state: IStore) => {
        state.pixelGraphs = [...virtuals]
      }),
      false,
      'ui/setPixelGraphs'
    ),
  viewMode: 'user',
  setViewMode: (mode: string): void =>
    set(
      produce((state: IStore) => {
        state.viewMode = mode
      }),
      false,
      'ui/setViewMode'
    ),
  // Cloud
  isLogged: false,
  setIsLogged: (logged: boolean) =>
    set(
      produce((state: IStore) => {
        state.isLogged = logged
      }),
      false,
      'general/setIsLogged'
    ),

  intro: true,
  setIntro: (intro: boolean) =>
    set(
      produce((state: IStore) => {
        state.intro = intro
      }),
      false,
      'general/setIsLogged'
    )
})

export default storeGeneral
