/* eslint-disable no-param-reassign */
import { produce } from 'immer'
import type { IStore } from '../useStore'

const storeUser = (set: any) => ({
  starred: {
    core: false,
    client: false,
    build: false
  },
  trophies: {
    fan: 0
  } as any,
  setStarred: (starred: any): void =>
    set(
      produce((state: IStore) => {
        state.user.starred = starred
      }),
      false,
      'setStarred'
    ),
  setStar: (repo: 'core' | 'client' | 'build', starred: boolean): void =>
    set(
      produce((state: IStore) => {
        state.user.starred[repo] = starred
      }),
      false,
      'setStarred'
    ),
  setTrophies: (name: string, trophy: number): void =>
    set(
      produce((state: IStore) => {
        state.user.trophies[name] = trophy
      }),
      false,
      'setStarred'
    )
})

export default storeUser
