/* eslint-disable no-extra-boolean-cast */
/* eslint-disable no-return-assign */
/* eslint-disable prettier/prettier */
import { useState, useEffect } from 'react'
import isElectron from 'is-electron';
import { Avatar, Dialog, Stack , CircularProgress } from '@mui/material'
import { CheckCircle } from '@mui/icons-material'
import {
  finishAuth,
  refreshAuth
} from '../../../utils/spotifyProxies'
import logoAsset from '../../../assets/logo.png'
import BladeIcon from '../../../components/Icons/BladeIcon/BladeIcon'


const baseURL = isElectron() ? 'http://localhost:8888' : window.location.href.split('/#')[0].replace(/\/+$/, '') || 'http://localhost:8888';
const storedURL = window.localStorage.getItem('ledfx-host');

const Circle = () => <div style={{ width: 32, height: 32, backgroundColor: 'transparent', border:'3px solid #fff', borderRadius: '50%' }}  />

const SpotifyLoginRedirect = () => {
  const [ready, setReady] = useState(false)

  useEffect(() => {
    finishAuth()
    refreshAuth()
    localStorage.setItem('Spotify-Token', window.location.search.replace('?code=', ''))
    setTimeout(() => { setReady(true) }, 1500)
    setTimeout( () =>
      (window.location.href = `${
        process.env.NODE_ENV === 'production'
          ? storedURL || baseURL
          : 'http://localhost:3000'
      }/#/Integrations?`),
    3000
    ) // Redirect to homepage after 3 sec
  }, [])


  return (<Dialog open fullScreen>
    <div style={{ margin: '4rem', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
      <Stack direction="row" spacing={2} marginBottom={5} alignItems="center">
        <Avatar sx={{ width: 120, height: 120, backgroundColor: 'transparent', border:'6px solid #fff', padding: '1rem' }} src={logoAsset} />
        <Circle />
        <Circle />
        <Avatar sx={{ width: 80, height: 80, backgroundColor: 'transparent', border:'6px solid #fff' }} >
          {ready ? (
            <CheckCircle color="success" sx={{ fontSize: '3rem' }} />
          ) : (
            <CircularProgress color="success" />
          )}
        </Avatar>
        <Circle />
        <Circle />
        <Avatar sx={{ width: 120, height: 120, backgroundColor: 'transparent', border:'6px solid #fff' }} >
          <BladeIcon
            name="mdi:spotify"
            style={{
              color: 'white',
              fontSize: '5rem',
              display: 'flex'
            }}
          />
        </Avatar>
      </Stack>
      {ready ? 'Successfully logged in with Spotify...' : 'Logging in with Spotify...'}
    </div>
  </Dialog>
  );
}

export default SpotifyLoginRedirect;
