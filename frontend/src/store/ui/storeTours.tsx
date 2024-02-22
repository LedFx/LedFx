/* eslint-disable no-param-reassign */
import { produce } from 'immer'
import type { IStore } from '../useStore'
// eslint-disable-next-line prettier/prettier
type ITours = 'home' | 'devices' | 'device' | 'effect' | 'integrations' | 'scenes' | 'settings';

const storeTours = (set: any) => ({
  tours: {
    home: false,
    devices: false,
    device: false,
    effect: false,
    integrations: false,
    scenes: false,
    settings: false
  },
  setTour: (tour: ITours): void =>
    set(
      produce((state: IStore) => {
        state.tours[tour] = true
      }),
      false,
      'ui/setTour'
    ),
  setTourOpen: (tour: ITours, open: boolean): void =>
    set(
      produce((state: IStore) => {
        state.tours[tour] = open
      }),
      false,
      'ui/setTour'
    )
})

export default storeTours
