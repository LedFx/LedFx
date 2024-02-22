/* eslint-disable react/jsx-no-useless-fragment */
import {
  HashRouter as Router,
  BrowserRouter,
  Routes,
  Route
} from 'react-router-dom'
import { useHotkeys } from 'react-hotkeys-hook'
import isElectron from 'is-electron'
import { Box, useTheme } from '@mui/material'
import ScrollToTop from '../utils/scrollToTop'
import '../App.css'

import LeftBar from '../components/Bars/BarLeft'
import TopBar from '../components/Bars/BarTop'
import BottomBar from '../components/Bars/BarBottom'
import MessageBar from '../components/Bars/BarMessage'
import NoHostDialog from '../components/Dialogs/NoHostDialog'
import Home from './Home/Home'
import Devices from './Devices/Devices'
import Device from './Device/Device'
import Scenes from './Scenes/Scenes'
import Settings from './Settings/Settings'
import Integrations from './Integrations/Integrations'
import LoginRedirect from './Login/LoginRedirect'
import SmartBar from '../components/Dialogs/SmartBar'
import useStore from '../store/useStore'
import SpotifyLoginRedirect from './Integrations/Spotify/SpotifyLoginRedirect'
import { drawerWidth, ios } from '../utils/helpers'
import User from './User/User'
import Lock from './Lock'
import Mp from '../components/Integrations/Spotify/Widgets/Mp/Mp'
import FrontendPixelsTooSmall from '../components/Dialogs/FrontendPixelsTooSmall'
import HostManager from '../components/Dialogs/HostManager'

const Routings = ({ handleWs }: any) => {
  const theme = useTheme()
  const isElect = isElectron()
  const mp = useStore((state) => state.ui.mp)
  const setMp = useStore((state) => state.ui.setMp)
  const setFeatures = useStore((state) => state.setFeatures)
  const setShowFeatures = useStore((state) => state.setShowFeatures)
  const smartBarOpen = useStore(
    (state) => state.ui.bars && state.ui.bars.smartBar.open
  )
  const setSmartBarOpen = useStore(
    (state) => state.ui.bars && state.ui.setSmartBarOpen
  )
  const leftBarOpen = useStore(
    (state) => state.ui.bars && state.ui.bars.leftBar.open
  )

  useHotkeys(['ctrl+alt+y', 'ctrl+alt+z'], () => setSmartBarOpen(!smartBarOpen))
  useHotkeys(['ctrl+alt+d'], () => setMp(!mp))
  useHotkeys(['ctrl+alt+g'], () => {
    if (window.localStorage.getItem('guestmode') === 'activated') {
      window.localStorage.removeItem('guestmode')
    } else {
      window.localStorage.setItem('guestmode', 'activated')
    }
    window.location.reload()
  })
  if (isElect) {
    useHotkeys(['ctrl+alt+l'], () => {
      window.localStorage.setItem('lock', 'activated')
      window.location.reload()
    })
  }
  useHotkeys(['ctrl+alt+a'], () => {
    setFeatures('beta', true)
    setFeatures('alpha', true)
    setShowFeatures('alpha', true)
    setShowFeatures('beta', true)
  })

  return (
    <>
      <ScrollToTop />
      {handleWs}
      <MessageBar />
      <TopBar />
      <LeftBar />
      <Box
        sx={{
          flexGrow: 1,
          background: 'transparent',
          padding: ios ? 0 : theme.spacing(0),
          transition: theme.transitions.create('margin', {
            easing: leftBarOpen
              ? theme.transitions.easing.easeOut
              : theme.transitions.easing.sharp,
            duration: leftBarOpen
              ? theme.transitions.duration.enteringScreen
              : theme.transitions.duration.leavingScreen
          }),
          marginLeft: leftBarOpen ? 0 : `-${drawerWidth}px`,
          '@media (max-width: 580px)': {
            padding: '8px'
          }
        }}
      >
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: theme.spacing(0, 1),
            ...theme.mixins.toolbar
          }}
        />
        <Routes>
          {window.localStorage.getItem('lock') === 'activated' && isElect ? (
            <Route path="*" element={<Lock />} />
          ) : (
            <>
              <Route
                path="/connect/:providerName/redirect"
                element={<LoginRedirect />}
              />
              <Route path="/" element={<Home />} />
              <Route path="/devices" element={<Devices />} />
              <Route path="/device/:virtId" element={<Device />} />
              <Route path="/scenes" element={<Scenes />} />
              {!(window.localStorage.getItem('guestmode') === 'activated') && (
                <Route path="/integrations" element={<Integrations />} />
              )}
              {!(window.localStorage.getItem('guestmode') === 'activated') && (
                <Route path="/settings" element={<Settings />} />
              )}
              <Route path="/user" element={<User />} />
              <Route
                path="*"
                element={
                  // eslint-disable-next-line prettier/prettier
                  !(window.localStorage.getItem('guestmode') === 'activated') ? <Home /> : <Scenes />
                }
              />
            </>
          )}
        </Routes>
        {mp && <Mp />}
        <NoHostDialog />
        <HostManager />
        <FrontendPixelsTooSmall />
        <SmartBar
          open={smartBarOpen}
          setOpen={setSmartBarOpen}
          direct={false}
        />
      </Box>
      {!(isElect && window.localStorage.getItem('lock') === 'activated') && (
        <BottomBar />
      )}
    </>
  )
}

const Pages = ({ handleWs }: any) => {
  return (
    <>
      {isElectron() ? (
        <Router>
          <Routings handleWs={handleWs} />
        </Router>
      ) : (
        <Router basename={process.env.PUBLIC_URL}>
          <Routings handleWs={handleWs} />
        </Router>
      )}

      <BrowserRouter>
        <Routes>
          <Route path="/callback" element={<SpotifyLoginRedirect />} />
          <Route path="*" element={<></>} />
        </Routes>
      </BrowserRouter>
    </>
  )
}

export default Pages
