/* eslint-disable no-param-reassign */
import { produce } from 'immer'
import type { IStore } from '../useStore'

const storeCloud = (set: any) => ({
  loginDialog: false,
  setLoginDialog: (open: boolean) => {
    set(
      produce((state: IStore) => {
        state.loginDialog = open
      }),
      false,
      'cloud/setLoginDialog'
    )
  }
})

export default storeCloud
