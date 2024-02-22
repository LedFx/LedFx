/* eslint-disable no-console */
import Cookies from 'universal-cookie/es6'
import axios from 'axios'
import isElectron from 'is-electron'
import qs from 'qs'
import { log } from './helpers'
import useStore from '../store/useStore'

const baseURL = isElectron()
  ? 'http://localhost:8888'
  : window.location.href.split('/#')[0].replace(/\/+$/, '') ||
    'http://localhost:8888'
const storedURL = window.localStorage.getItem('ledfx-host')
const redirectUrl = `${
  process.env.NODE_ENV === 'production'
    ? storedURL || baseURL
    : 'http://localhost:3000'
}/callback/#/Integrations?`

axios.create({
  baseURL: redirectUrl
})

const apiCredentials = {
  CLIENT_ID: '7658827aea6f47f98c8de593f1491da5',
  // CLIENT_SECRET: '',
  REDIRECT_URL: redirectUrl,
  SCOPES: [
    // Users (Review later if needed)
    'user-top-read',
    'user-read-email',
    'user-read-private',
    // Playback
    'streaming',
    'user-read-playback-position',
    // Spotify Connect
    'user-read-playback-state',
    'user-modify-playback-state',
    'user-read-currently-playing',
    // Listening History (resume playback)
    'user-read-recently-played',
    // Library
    'user-library-read',
    'user-library-modify'
  ]
}

export const finishAuth = async () => {
  log('successSpotify', 'finishAuth')
  // const search = window.location.search.substring(1);
  const params = localStorage.getItem('Spotify-Token')
  const cookies = new Cookies()
  const postData = {
    client_id: '7658827aea6f47f98c8de593f1491da5',
    grant_type: 'authorization_code',
    code: params,
    redirect_uri: apiCredentials.REDIRECT_URL,
    code_verifier: cookies.get('verifier')
  }
  const config = {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  }
  return axios
    .post(
      'https://accounts.spotify.com/api/token',
      // encodeURI(JSON.stringify(postData)),
      qs.stringify(postData),
      config
    )
    .then((res) => {
      const tokens = {} as any
      const expDate = new Date()
      expDate.setHours(expDate.getHours() + 1)
      cookies.remove('access_token')
      cookies.remove('logout', { path: '/#' })
      cookies.remove('logout', { path: '/#/integrations' })

      cookies.set('access_token', res.data.access_token, { expires: expDate })
      cookies.set('logout', false)
      tokens.accessToken = res.data.access_token

      const refreshExpDate = new Date()
      refreshExpDate.setDate(refreshExpDate.getDate() + 7)
      cookies.remove('refresh_token')
      cookies.set('refresh_token', res.data.refresh_token, {
        expires: refreshExpDate
      })
      tokens.refreshToken = res.data.refresh_token
      cookies.remove('verifier')
      localStorage.removeItem('Spotify-Token')
      window.history.replaceState({}, document.title, '/#/integrations')
      return tokens
    })
    .catch((e) => console.log(e))
}

export async function refreshAuth() {
  log('successSpotify', 'refreshAuth')
  const cookies = new Cookies()
  // const access_token = cookies.get('access_token')
  const refresh_token = cookies.get('refresh_token')

  const postData = {
    client_id: '7658827aea6f47f98c8de593f1491da5',
    grant_type: 'refresh_token',
    refresh_token
  }

  if (!refresh_token) {
    console.error('Refresh Token is not defined')
    return 'Error'
  }
  // if (!access_token) {
  //   console.error('Access Token is not defined')
  //   return 'Error'
  // }

  const config = {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  }

  try {
    const res = await axios.post(
      'https://accounts.spotify.com/api/token',
      qs.stringify(postData),
      config
    )

    const freshTokens = {} as any
    const expDate = new Date()
    expDate.setHours(expDate.getHours() + 1)

    cookies.remove('access_token', { path: '/integrations' })
    cookies.set('access_token', res.data.access_token, { expires: expDate })
    freshTokens.accessToken = res.data.access_token

    const refreshExpDate = new Date()
    refreshExpDate.setDate(refreshExpDate.getDate() + 7)
    cookies.remove('refresh_token', { path: '/integrations' })
    cookies.set('refresh_token', res.data.refresh_token, {
      expires: refreshExpDate
    })
    freshTokens.refreshToken = res.data.refreshToken
    const res2 = await axios.get('https://api.spotify.com/v1/me', {
      headers: {
        Authorization: `Bearer ${freshTokens.accessToken}`
      }
    })
    if (res2.status === 200) {
      return res2.data
    }
    return freshTokens
  } catch (error) {
    console.log(error)
    return 'Error'
  }
}

export function logoutAuth() {
  log('successSpotify', 'starting logoutAuth')
  const cookies = new Cookies()
  cookies.remove('logout', { path: '/' })
  cookies.remove('logout', { path: '/integrations' })
  cookies.remove('access_token', { path: '/' })
  cookies.remove('access_token', { path: '/integrations' })

  cookies.remove('refresh_token', { path: '/integrations' })
  cookies.remove('refresh_token', { path: '/' })

  cookies.remove('logout')

  cookies.set('logout', true)
  return true
}

// Helper function to wait for the access_token cookie to be defined
function waitForAccessToken(timeout: number) {
  log('successSpotify', 'starting waitForAccessToken')
  return new Promise<void>((resolve, reject) => {
    const startTime = Date.now()
    const interval = setInterval(() => {
      const cookies = new Cookies()
      const access_token = cookies.get('access_token')
      if (access_token) {
        clearInterval(interval)
        resolve()
      } else if (Date.now() - startTime >= timeout) {
        clearInterval(interval)
        window.location.reload()
        reject(new Error('Access Token not defined after waiting timeout'))
      }
    }, 100)
  })
}

export async function spotifyMe() {
  const cookies = new Cookies()
  let access_token = cookies.get('access_token')

  if (!access_token) {
    // Wait for 10 seconds for the access_token cookie to be defined; otherwise, throw an error
    await waitForAccessToken(10000)
    access_token = cookies.get('access_token')
  }

  if (!access_token) {
    console.error('Access Token is not defined')
    return 'Error'
  }

  const res = await axios.get('https://api.spotify.com/v1/me', {
    headers: {
      Authorization: `Bearer ${access_token}`
    }
  })

  if (res.status === 200) {
    return res.data
  }

  return 'Error'
}
export async function spotifyCurrentTime() {
  const cookies = new Cookies()
  let access_token = cookies.get('access_token')

  if (!access_token) {
    // Wait for 10 seconds for the access_token cookie to be defined; otherwise, throw an error
    await waitForAccessToken(10000)
    access_token = cookies.get('access_token')
  }

  if (!access_token) {
    console.error('Access Token is not defined')
    return 'Error'
  }

  const res = await axios.get(
    'https://api.spotify.com/v1/me/player/currently-playing',
    {
      headers: {
        Authorization: `Bearer ${access_token}`
      }
    }
  )

  if (res.status === 200) {
    return res.data
  }

  return 'Error'
}
export async function spotifyGetDevices() {
  const cookies = new Cookies()
  let access_token = cookies.get('access_token')

  if (!access_token) {
    // Wait for 10 seconds for the access_token cookie to be defined; otherwise, throw an error
    await waitForAccessToken(10000)
    access_token = cookies.get('access_token')
  }

  if (!access_token) {
    console.error('Access Token is not defined')
    return 'Error'
  }

  const res = await axios.get('https://api.spotify.com/v1/me/player/devices', {
    headers: {
      Authorization: `Bearer ${access_token}`
    }
  })

  if (res.status === 200) {
    return res.data
  }

  return 'Error'
}
// export async function spotifyTogglePlay(id: string) {
//   console.log('starting spotifyTogglePlay')
//   const cookies = new Cookies()
//   let access_token = cookies.get('access_token')

//   if (!access_token) {
//     // Wait for 10 seconds for the access_token cookie to be defined; otherwise, throw an error
//     await waitForAccessToken(10000)
//     access_token = cookies.get('access_token')
//   }

//   if (!access_token) {
//     console.error('Access Token is not defined')
//     return 'Error'
//   }

//   const res = await axios.get('https://api.spotify.com/v1/me/player/play', {
//     headers: {
//       Authorization: `Bearer ${access_token}`
//     }
//   })

//   if (res.status === 200) {
//     return res.data
//   }

//   return 'Error'
// }

export async function spotifyPause() {
  const cookies = new Cookies()
  const res = await axios.put(
    'https://api.spotify.com/v1/me/player/pause',
    {},
    {
      headers: {
        Authorization: `Bearer ${cookies.get('access_token')}`
      }
    }
  )
  if (res.status === 200) {
    return 'Success'
  }
  return 'Error'
}

export async function spotifyPlay(deviceId: string) {
  const cookies = new Cookies()
  try {
    const res = await axios.put(
      'https://api.spotify.com/v1/me/player',
      { device_ids: [deviceId], play: true },
      {
        headers: {
          Authorization: `Bearer ${cookies.get('access_token')}`
        }
      }
    )
    if (res.status === 200) {
      return 'Success'
    }
    return 'Error'
  } catch (error) {
    return log('Spotify', error)
  }
}

export async function spotifyPlayOnly(deviceId: string) {
  const cookies = new Cookies()
  const res = await axios.put(
    `https://api.spotify.com/v1/me/player/play?device_id=${deviceId}`,
    {},
    {
      headers: {
        Authorization: `Bearer ${cookies.get('access_token')}`
      }
    }
  )
  if (res.status === 200) {
    return 'Success'
  }
  return 'Error'
}

export async function spotifyPlaySong(
  deviceId: string,
  id: string,
  position_ms?: number,
  context?: string
) {
  const cookies = new Cookies()
  try {
    const res = await axios.put(
      `https://api.spotify.com/v1/me/player/play?device_id=${deviceId}`,
      {
        uris: context ? undefined : [`spotify:track:${id}`],
        position_ms: position_ms || 0,
        context_uri: context && context !== '' ? context : undefined,
        offset: context ? { uri: `spotify:track:${id}` } : undefined
      },
      {
        headers: {
          Authorization: `Bearer ${cookies.get('access_token')}`
        }
      }
    )
    if (res.status === 200) {
      return 'Success'
    }
    return 'Error'
  } catch (_error) {
    const { showSnackbar } = useStore.getState().ui
    showSnackbar('error', 'Song is not available')
    return 'Error'
  }
}
export async function spotifyRepeat(deviceId: string, mode: number) {
  const cookies = new Cookies()
  const res = await axios.put(
    `https://api.spotify.com/v1/me/player/repeat?state=${
      mode === 0 ? 'context' : mode === 1 ? 'track' : 'off'
    }&device_id=${deviceId}`,
    {},
    {
      headers: {
        Authorization: `Bearer ${cookies.get('access_token')}`
      }
    }
  )
  if (res.status === 200) {
    return 'Success'
  }
  return 'Error'
}
export async function spotifyShuffle(deviceId: string, state: any) {
  const cookies = new Cookies()
  const res = await axios.put(
    `https://api.spotify.com/v1/me/player/shuffle?state=${JSON.stringify(
      state
    )}&device_id=${deviceId}`,
    {},
    {
      headers: {
        Authorization: `Bearer ${cookies.get('access_token')}`
      }
    }
  )
  if (res.status === 200) {
    return 'Success'
  }
  return 'Error'
}

export async function addTrigger(trigger: any) {
  const res = await axios.post(
    `${storedURL || baseURL}/api/integrations/spotify/spotify`,
    trigger
  )
  if (res.status === 200) {
    return 'Success'
  }
  return 'Error'
}

export async function getTrackFeatures(id: string, token: string) {
  const res = await axios.get(
    `https://api.spotify.com/v1/audio-features/${id}`,
    {
      headers: {
        Authorization: `Bearer ${token}`
      }
    }
  )
  if (res.status === 200) {
    return res.data
  }
  return 'Error'
}

export async function getTrackArtist(id: string, token: string) {
  const res = await axios.get(`https://api.spotify.com/v1/artists/${id}`, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  })
  if (res.status === 200) {
    return res.data
  }
  return 'Error'
}

export async function getTrackAnalysis(id: string, token: string) {
  const res = await axios.get(
    `https://api.spotify.com/v1/audio-analysis/${id}`,
    {
      headers: {
        Authorization: `Bearer ${token}`
      }
    }
  )
  if (res.status === 200) {
    return res.data
  }
  return 'Error'
}

export function fixAnalysis(audioAnalysis: any) {
  const new_analysis = { ...audioAnalysis }

  new_analysis.segments = []
  if (audioAnalysis?.segments) {
    audioAnalysis.segments.forEach((segment: any) => {
      const new_segment = { ...segment }
      new_segment.start = parseFloat(segment.start.toFixed(2))
      new_segment.pitches = []
      let pitchTotal = 0
      console.log(segment.pitches)
      segment.pitches.forEach((pitch: number) => {
        console.log(pitch)
        pitchTotal += pitch
      })
      segment.pitches.forEach((pitch: number) => {
        const new_pitch = (pitch / pitchTotal) * 100
        new_segment.pitches.push(new_pitch)
      })

      new_analysis.segments.push(new_segment)
    })
  }

  return new_analysis
}

export async function getPlaylist(id: string, token: string) {
  const res = await axios.get(
    `https://api.spotify.com/v1/playlists/${id}/tracks`,
    {
      headers: {
        Authorization: `Bearer ${token}`
      }
    }
  )
  if (res.status === 200) {
    return res.data
  }
  return 'Error'
}

export async function getPlaylistB(id: string, token: string) {
  const res = await axios.get(`https://api.spotify.com/v1/playlists/${id}`, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  })
  if (res.status === 200) {
    return res.data
  }
  return 'Error'
}
