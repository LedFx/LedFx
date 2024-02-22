/* eslint-disable no-param-reassign */
import { produce } from 'immer'
import type { IStore } from '../useStore'

const storeNotifications = (set: any) => ({
  updateNotificationInterval: 1440,
  setUpdateNotificationInterval: (ms: number): void =>
    set(
      produce((state: IStore) => {
        state.updateNotificationInterval = ms
      }),
      false,
      'setUpdateNotificationInterval'
    )
})

export default storeNotifications
