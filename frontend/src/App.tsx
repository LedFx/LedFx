/* eslint-disable @typescript-eslint/indent */
import { useEffect, useMemo } from 'react'
import { createTheme, ThemeProvider } from '@mui/material/styles'
import { SnackbarProvider } from 'notistack'
import isElectron from 'is-electron'
import { Box, CssBaseline } from '@mui/material'
import Cookies from 'universal-cookie/es6'
import ws, { WsContext, HandleWs } from './utils/Websocket'
import useStore from './store/useStore'
import useWindowDimensions from './utils/useWindowDimension'
import './App.css'
import { deleteFrontendConfig, initFrontendConfig } from './utils/helpers'
import WaveLines from './components/Icons/waves'
import Pages from './pages/Pages'
import SpotifyProvider from './components/Integrations/Spotify/SpotifyProvider'
import { ledfxThemes, ledfxTheme, common } from './themes/AppThemes'
import xmas from './assets/xmas.png'
import newyear from './assets/fireworks.jpg'
import login from './utils/login'

export default function App() {
  const { height, width } = useWindowDimensions()
  const features = useStore((state) => state.features)
  const protoCall = useStore((state) => state.protoCall)
  const setProtoCall = useStore((state) => state.setProtoCall)
  const setPlatform = useStore((state) => state.setPlatform)
  const getVirtuals = useStore((state) => state.getVirtuals)
  const getSystemConfig = useStore((state) => state.getSystemConfig)
  const getSchemas = useStore((state) => state.getSchemas)
  const shutdown = useStore((state) => state.shutdown)
  const showSnackbar = useStore((state) => state.ui.showSnackbar)
  const darkMode = useStore((state) => state.ui.darkMode)
  const setCoreParams = useStore((state) => state.setCoreParams)
  const setCoreStatus = useStore((state) => state.setCoreStatus)

  const theme = useMemo(
    () =>
      createTheme({
        ...ledfxThemes[ledfxTheme],
        ...common,
        palette: {
          ...ledfxThemes[ledfxTheme].palette
          // mode: darkMode ? 'dark' : 'light',
          // background: darkMode
          //   ? {
          //       default: '#030303',
          //       paper: '#151515',
          //     }
          //   : {
          //       default: '#bbb',
          //       paper: '#fefefe',
          //     },
        }
      }),
    [darkMode]
  )

  useEffect(() => {
    getVirtuals()
    getSystemConfig()
    getSchemas()
  }, [getVirtuals, getSystemConfig, getSchemas])

  useEffect(() => {
    initFrontendConfig()
    // eslint-disable-next-line no-console
    console.info(
      // eslint-disable-next-line no-useless-concat
      '%c Ledfx ' + '%c\n ReactApp by Blade ',
      'padding: 10px 40px; color: #ffffff; border-radius: 5px 5px 0 0; background-color: #800000;',
      'background: #fff; color: #800000; border-radius: 0 0 5px 5px;padding: 5px 0;'
    )
    if (window.location.pathname.includes('hassio_ingress'))
      // eslint-disable-next-line no-console
      console.info(
        // eslint-disable-next-line no-useless-concat
        '%c HomeAssistant detected ',
        'padding: 3px 5px; border-radius: 5px; color: #ffffff; background-color: #038fc7;'
      )
    if (isElectron()) {
      ;(window as any)?.api?.send('toMain', { command: 'get-platform' })
      ;(window as any)?.api?.send('toMain', { command: 'get-core-params' })
    }
  }, [])
  ;(window as any).api?.receive('fromMain', (parameters: any) => {
    if (parameters === 'shutdown') {
      shutdown()
    }
    if (parameters[0] === 'platform') {
      setPlatform(parameters[1])
    }
    if (parameters[0] === 'currentdir') {
      // eslint-disable-next-line no-console
      console.log(parameters[1])
    }
    if (parameters[0] === 'protocol') {
      // console.log('protocol', parameters[1])
      setProtoCall(JSON.parse(parameters[1]).commandLine.pop())
    }
    if (parameters[0] === 'snackbar') {
      showSnackbar('info', parameters[1])
    }
    if (parameters[0] === 'coreParams') {
      // console.log('coreParams', parameters[1])
      setCoreParams(parameters[1])
    }
    if (parameters[0] === 'status') {
      // console.log('status', parameters[1])
      setCoreStatus(parameters[1])
    }
    if (parameters === 'clear-frontend') {
      deleteFrontendConfig()
    }
    if (parameters === 'all-windows') {
      // console.log('all-windows', parameters[1])
    }
  })

  useEffect(() => {
    const handleWebsockets = (e: any) => {
      showSnackbar(e.detail.type, e.detail.message)
    }
    document.addEventListener('YZNEW', handleWebsockets)
    return () => {
      document.removeEventListener('YZNEW', handleWebsockets)
    }
  }, [])

  useEffect(() => {
    if (protoCall !== '') {
      // showSnackbar('info', `External call: ${protoCall}`)
      const proto = protoCall.split('/').filter((n) => n)
      // eslint-disable-next-line no-console
      console.table({
        Domain: proto[1],
        Action: proto[2],
        Payload: proto[3]
      })
      if (proto[1] === 'callback') {
        const cookies = new Cookies()
        const expDate = new Date()
        expDate.setHours(expDate.getHours() + 1)
        cookies.remove('access_token', { path: '/integrations' })
        cookies.set(
          'access_token',
          proto[2].replace('?code=', '').replace('#%2FIntegrations%3F', ''),
          { expires: expDate }
        )
      } else if (proto[1] === 'auth') {
        login(proto.join().split('redirect?')[1]).then(() => {
          window.location.reload()
        })
      } else {
        showSnackbar('info', `External call: ${protoCall}`)
      }
      setProtoCall('')
    }
  }, [protoCall, showSnackbar])

  return (
    <ThemeProvider theme={theme}>
      <SnackbarProvider maxSnack={15}>
        <WsContext.Provider value={ws}>
          <SpotifyProvider>
            <Box
              sx={{ display: 'flex' }}
              style={{ paddingTop: isElectron() ? '30px' : 0 }}
            >
              <CssBaseline />
              <Pages handleWs={<HandleWs />} />
            </Box>
          </SpotifyProvider>
        </WsContext.Provider>
        {features.waves && (
          <WaveLines
            startColor={theme.palette.primary.main}
            stopColor={theme.palette.accent.main || '#ffdc0f'}
            width={width - 8}
            height={height}
          />
        )}
        {new Date().getFullYear() === 2023 && (
          <div
            style={{
              margin: 'auto',
              backgroundImage: `url(${xmas})`,
              backgroundSize: 'cover',
              backgroundRepeat: 'no-repeat',
              backgroundPosition: 'bottom',
              display: 'block',
              zIndex: -1,
              position: 'fixed',
              top: 0,
              right: 0,
              bottom: 0,
              left: 0,
              opacity: 0.7
            }}
          />
        )}
        {new Date().getFullYear() === 2024 &&
          new Date().getMonth() === 0 &&
          new Date().getDate() === 1 && (
            <div
              style={{
                margin: 'auto',
                backgroundImage: `url(${newyear})`,
                backgroundSize: 'contain',
                backgroundRepeat: 'no-repeat',
                backgroundPosition: 'bottom right',
                display: 'block',
                zIndex: -1,
                position: 'fixed',
                top: 0,
                right: 0,
                bottom: 0,
                left: 0,
                opacity: 0.7
              }}
            />
          )}
      </SnackbarProvider>
    </ThemeProvider>
  )
}
