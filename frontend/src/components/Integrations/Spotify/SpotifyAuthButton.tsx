/* eslint-disable prettier/prettier */
/* eslint-disable no-unused-vars */
/* eslint-disable @typescript-eslint/no-unused-vars */
import { useState, useEffect } from 'react'
import Button from '@mui/material/Button'
import axios from 'axios'
import Cookies from 'universal-cookie/es6'
import getPkce from 'oauth-pkce'
import isElectron from 'is-electron'
import { Login, Logout } from '@mui/icons-material'
import useStore from '../../../store/useStore'
import {
  finishAuth,
  refreshAuth,
  logoutAuth
} from '../../../utils/spotifyProxies'
import useIntegrationCardStyles from '../../../pages/Integrations/IntegrationCard/IntegrationCard.styles'
import { log } from '../../../utils/helpers'

// eslint-disable-next-line prettier/prettier
const baseURL = isElectron() ? 'http://localhost:8888' : window.location.href.split('/#')[0].replace(/\/+$/, '') || 'http://localhost:8888';
// const baseURL = isElectron() ? 'http://localhost:8888' : window.location.href.split('/#')[0].replace(/\/+$/, '') || 'http://localhost:8888';
const storedURL = window.localStorage.getItem('ledfx-host')
const redirectUrl = `${
  process.env.NODE_ENV === 'production'
    ? isElectron()
      ? baseURL
      : storedURL || baseURL
    : isElectron()
      ? baseURL
      : 'http://localhost:3000'
}/callback/#/Integrations?`

// const spotify = axios.create({
//   baseURL: redirectUrl,
// });

const apiCredentials = {
  CLIENT_ID: '7658827aea6f47f98c8de593f1491da5',
  // CLIENT_SECRET: '',
  REDIRECT_URL: decodeURIComponent(redirectUrl),
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

const SpotifyAuthButton = ({ disabled = false }: any) => {
  const spAuthenticated = useStore((state) => state.spotify.spAuthenticated)
  const player = useStore((state) => state.spotify.player)
  const setspAuthenticated = useStore((state) => state.setSpAuthenticated)
  const setSpotifyAuthToken = useStore((state) => state.setSpAuthToken)
  const [codes, setCodes] = useState({})
  const cookies = new Cookies()
  const classes = useIntegrationCardStyles()
  useEffect(() => {
    getPkce(50, (_error: any, { verifier, challenge }: any) => {
      setCodes({ verifier, challenge })
    })
    if (cookies.get('access_token')) {
      setspAuthenticated(true)
    }
  }, [])
  const beginAuth = () => {
    cookies.set('verifier', (codes as any).verifier)
    const authURL =
      'https://accounts.spotify.com/authorize/' +
      '?response_type=code' +
      `&client_id=${encodeURIComponent(
        '7658827aea6f47f98c8de593f1491da5'
      )}&scope=${encodeURIComponent(
        'user-library-read user-library-modify user-read-email user-top-read streaming user-read-private user-read-playback-state user-modify-playback-state'
      )}&redirect_uri=${encodeURIComponent(
        apiCredentials.REDIRECT_URL
      )}&code_challenge=${encodeURIComponent(
        (codes as any).challenge
      )}&code_challenge_method=S256`
    if (window.location.pathname.includes('hassio_ingress')) {
      window.location.href = authURL
    } else {
      window.open(authURL, '_blank', 'noopener,noreferrer')
    }
  }

  useEffect(() => {
    const accessTest = cookies.get('logout')
    const accessTest1 = cookies.get('access_token')
    if ((accessTest === 'false' || !accessTest) && !accessTest1) {
      refreshAuth()
      cookies.set('logout', false)
      setspAuthenticated(true)
    }
    if (localStorage.getItem('Spotify-Token')) {
      setspAuthenticated(true)

      try {
        finishAuth()
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn(err)
      }
    }
  }, [])

  useEffect(() => {
    if (cookies.get('access_token')) {
      setspAuthenticated(true)
      setSpotifyAuthToken(cookies.get('access_token'))
    } else {
      setspAuthenticated(false)
    }
  }, [cookies])

  return !spAuthenticated ? (
    <Button
      disabled={disabled}
      size="small"
      color="inherit"
      className={classes.editButton}
      onClick={() => {
        beginAuth()
      }}
    >
      <Login />
    </Button>
  ) : (
    <Button
      disabled={disabled}
      size="small"
      color="inherit"
      className={classes.editButton}
      onClick={() => {
        logoutAuth()
        if (player) player.disconnect()
        setspAuthenticated(false)
        setSpotifyAuthToken(false)
      }}
    >
      <Logout />
    </Button>
  )
}

export default SpotifyAuthButton
