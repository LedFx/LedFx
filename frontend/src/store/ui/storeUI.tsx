/* eslint-disable no-param-reassign */
import { produce } from 'immer'
import { VariantType } from 'notistack'
import pkg from '../../../package.json'
import type { IStore } from '../useStore'

const storeUI = (set: any) => ({
  effectDescriptions: 'Hide' as 'Auto' | 'Show' | 'Hide',
  setEffectDescriptions: (mode: 'Auto' | 'Show' | 'Hide'): void =>
    set(
      produce((state: IStore) => {
        state.ui.effectDescriptions = mode
      }),
      false,
      'ui/effectDescriptions'
    ),
  showHex: false,
  setShowHex: (show: boolean): void =>
    set(
      produce((state: IStore) => {
        state.ui.showHex = show
      }),
      false,
      'ui/showHex'
    ),
  mp: false,
  setMp: (mp: boolean): void =>
    set(
      produce((state: IStore) => {
        state.ui.mp = mp
      }),
      false,
      'ui/mp'
    ),
  latestTag: pkg.version as string,
  setLatestTag: (tag: string): void =>
    set(
      produce((state: IStore) => {
        state.ui.latestTag = tag
      }),
      false,
      'setLatestTag'
    ),

  darkMode: true,
  setDarkMode: (dark: boolean): void =>
    set(
      produce((state: IStore) => {
        state.ui.darkMode = dark
      }),
      false,
      'ui/darkmode'
    ),
  infoAlerts: {
    scenes: true,
    devices: true,
    user: true,
    gamepad: true
  },
  setInfoAlerts: (
    key: 'scenes' | 'devices' | 'user' | 'gamepad',
    val: boolean
  ): void =>
    set(
      produce((state: IStore) => {
        state.ui.infoAlerts[key] = val
      }),
      false,
      'ui/setInfoAlerts'
    ),
  snackbar: {
    isOpen: false,
    messageType: 'error' as VariantType,
    message: 'NO MESSAGE'
  },
  showSnackbar: (messageType: VariantType, message: string): void =>
    set(
      produce((state: IStore) => {
        state.ui.snackbar = { isOpen: true, message, messageType }
      }),
      false,
      'ui/showSnackbar'
    ),
  clearSnackbar: (): void =>
    set(
      produce((state: IStore) => {
        state.ui.snackbar.isOpen = false
      }),
      false,
      'ui/clearSnackbar'
    ),
  bars: {
    leftBar: {
      open: false
    },
    smartBar: {
      open: false
    },
    smartBarPad: {
      open: false
    },
    bottomBar: [] as any
  },
  setLeftBarOpen: (open: boolean): void =>
    set(
      produce((state: IStore) => {
        state.ui.bars.leftBar.open = open
      }),
      false,
      'ui/setLeftBarOpen'
    ),
  setBottomBarOpen: (page: string): void =>
    set(
      produce((state: IStore) => {
        if (state.ui.bars.bottomBar.indexOf(page) === -1) {
          state.ui.bars.bottomBar = [...state.ui.bars.bottomBar, page]
        } else {
          state.ui.bars.bottomBar = state.ui.bars.bottomBar.filter(
            (p: any) => p !== page
          )
        }
      }),
      false,
      'ui/setBottomBarOpen'
    ),
  setSmartBarOpen: (open: boolean): void =>
    set(
      produce((state: IStore) => {
        state.ui.bars.smartBar.open = open
      }),
      false,
      'ui/setSmartBarOpen'
    ),
  setSmartBarPadOpen: (open: boolean): void =>
    set(
      produce((state: IStore) => {
        state.ui.bars.smartBarPad.open = open
      }),
      false,
      'ui/setSmartBarOpen'
    ),

  settingsExpanded: 'false',
  setSettingsExpanded: (setting: any): void =>
    set(
      produce((state: IStore) => {
        state.ui.settingsExpanded = setting
      }),
      false,
      'ui/settingsExpanded'
    ),
  sceneActiveTags: [] as string[],
  toggletSceneActiveTag: (tag: string): void =>
    set(
      produce((state: IStore) => {
        state.ui.sceneActiveTags = state.ui.sceneActiveTags.includes(tag)
          ? state.ui.sceneActiveTags.filter((t: string) => t !== tag)
          : [...state.ui.sceneActiveTags, tag]
      }),
      false,
      'ui/settingsExpanded'
    )
})

export default storeUI
