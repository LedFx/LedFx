/* eslint-disable no-param-reassign */
import { produce } from 'immer'

const storeYoutube = (set: any) => ({
  youtubeURL:
    'https://www.youtube.com/watch?v=s6Yyb3N9IuA&list=PLD579BDF7F8D8BFE0',
  setYoutubeURL: (url: string) => {
    set(
      produce((state: any) => {
        state.youtube.youtubeURL = url
      }),
      false,
      'youtube/setYoutubeURL'
    )
  }
})

export default storeYoutube
