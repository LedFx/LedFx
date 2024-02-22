import { spDevice } from './SpState'
import { SpotifyState } from './SpotifyState'

const storeSpotify = () => ({
  spotifyEmbedUrl:
    'https://open.spotify.com/embed/playlist/4sXMBGaUBF2EjPvrq2Z3US?',
  spotifyAuthToken: '',
  player: null as any,
  swSize: 'small',
  swX: 50,
  swY: 200,
  swWidth: 300,
  spNetworkTime: 1000,
  spAuthenticated: false,
  spotifyData: {} as any,
  spotifyDevice: {} as any,
  spotifyDevices: [] as spDevice[],
  spotifytriggers: {},
  spTriggersList: [] as any,
  spActTriggers: [] as string[],
  playlist: [] as any,
  me: {} as any,
  spotifyState: {} as SpotifyState,
  spotifyVol: 0,
  spotifyPos: null as any,
  spotify: null as any
})

export default storeSpotify
