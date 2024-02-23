/* eslint-disable no-param-reassign */
import { produce } from 'immer'
import type { IStore } from '../useStore'

interface IButtonMapping {
  scene?: string
  command?: string
  payload?: any
}

interface IDefaultMapping {
  [key: number]: IButtonMapping
}

const defaultMapping = {
  0: {
    mode: 'command',
    command: 'play/pause'
  },
  9: {
    mode: 'command',
    command: 'padscreen'
  },
  12: {
    mode: 'command',
    command: 'brightness-up'
  },
  13: {
    mode: 'command',
    command: 'brightness-down'
  }
} as IDefaultMapping

interface IMapping {
  [key: number]: IDefaultMapping
}

const storePad = (set: any) => ({
  mapping: {
    0: defaultMapping,
    1: defaultMapping,
    2: defaultMapping,
    3: defaultMapping
  } as IMapping,
  analogBrightness: {
    0: false,
    1: false,
    2: false,
    3: false
  },
  blocked: false,
  setMapping: (mapping: IMapping): void =>
    set(
      produce((state: IStore) => {
        state.mapping = mapping
      }),
      false,
      'setMapping'
    ),
  setAnalogBrightness: (analogBrightness: any): void =>
    set(
      produce((state: IStore) => {
        state.analogBrightness = analogBrightness
      }),
      false,
      'setAnalogBrightness'
    ),
  setBlocked: (blocked: boolean): void =>
    set(
      produce((state: IStore) => {
        state.blocked = blocked
      }),
      false,
      'setBlocked'
    )
})

export default storePad
