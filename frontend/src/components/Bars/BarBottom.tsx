/* eslint-disable @typescript-eslint/indent */
import { useState, useEffect } from 'react'
import {
  BottomNavigation,
  BottomNavigationAction,
  Backdrop,
  useTheme
} from '@mui/material'
import {
  Settings,
  Home,
  // Wallpaper,
  // SettingsInputSvideo,
  // SettingsInputComponent,
  Dashboard,
  ElectricalServices
} from '@mui/icons-material'
import { useLocation, Link } from 'react-router-dom'
import useStore from '../../store/useStore'
import AddSceneDialog from '../Dialogs/SceneDialogs/AddSceneDialog'
import AddDeviceDialog from '../Dialogs/AddDeviceDialog'
import AddVirtualDialog from '../Dialogs/AddVirtualDialog'
import AddIntegrationDialog from '../Dialogs/AddIntegrationDialog'
import SpotifyFabFree from '../Integrations/Spotify/SpotifyFabFree'
import AddButton from '../AddButton/AddButton'
import YoutubeWidget from '../Integrations/Youtube/YoutubeWidget'
import SpotifyFabPro from '../Integrations/Spotify/SpotifyFabPro'
import MIDIListener from '../MidiInput'
import { drawerWidth, ios } from '../../utils/helpers'
import EditSceneDialog from '../Dialogs/SceneDialogs/EditSceneDialog'
import BladeIcon from '../Icons/BladeIcon/BladeIcon'
import AddWledDialog from '../Dialogs/AddWledDialog'
import Gamepad from '../Gamepad/Gamepad'
import SmartBar from '../Dialogs/SmartBar'

export default function BarBottom() {
  const theme = useTheme()
  const { pathname } = useLocation()
  const [value, setValue] = useState(pathname)
  const [backdrop, setBackdrop] = useState(false)
  const leftOpen = useStore(
    (state) => state.ui.bars && state.ui.bars?.leftBar.open
  )
  const bottomBarOpen = useStore(
    (state) => state.ui.bars && state.ui.bars?.bottomBar
  )

  const features = useStore((state) => state.features)
  const integrations = useStore((state) => state.integrations)
  const activateScene = useStore((state) => state.activateScene)
  const captivateScene = useStore((state) => state.captivateScene)
  const smartBarPadOpen = useStore(
    (state) => state.ui.bars && state.ui.bars.smartBarPad.open
  )
  const setSmartBarPadOpen = useStore(
    (state) => state.ui.bars && state.ui.setSmartBarPadOpen
  )
  const scenes = useStore((state) => state.scenes)
  const handleActivateScene = (e: string) => {
    activateScene(e)
    if (scenes[e]?.scene_puturl && scenes[e]?.scene_payload)
      captivateScene(scenes[e]?.scene_puturl, scenes[e]?.scene_payload)
  }
  const [spotifyEnabled, setSpotifyEnabled] = useState(false)
  const [spotifyExpanded, setSpotifyExpanded] = useState(false)
  const spotifyURL = useStore((state) => state.spotify.spotifyEmbedUrl)
  const setSpotifyURL = useStore((state) => state.setSpEmbedUrl)

  const [youtubeEnabled, setYoutubeEnabled] = useState(false)
  const [youtubeExpanded, setYoutubeExpanded] = useState(false)
  const youtubeURL = useStore((state) => state.youtubeURL)
  const setYoutubeURL = useStore((state) => state.setYoutubeURL)

  const [botHeight, setBotHeight] = useState(0)
  const spAuthenticated = useStore((state) => state.spotify.spAuthenticated)

  useEffect(() => {
    let height = 0
    if (spotifyEnabled) {
      height += 80
    }
    if (spotifyExpanded) {
      height += 220
    }
    if (youtubeEnabled) {
      height += 80
    }
    if (youtubeExpanded) {
      height += 220
    }
    setBotHeight(height)
  }, [spotifyEnabled, spotifyExpanded, youtubeEnabled, youtubeExpanded])

  useEffect(() => {
    setValue(pathname)
  }, [pathname])

  return (
    <>
      <BottomNavigation
        value={value}
        sx={{
          width: leftOpen ? `calc(100% - ${drawerWidth}px)` : '100%',
          marginLeft: leftOpen ? `${drawerWidth}px` : 0,
          height: ios ? 80 : 56,
          paddingBottom: ios ? '16px' : 0,
          paddingTop: ios ? '8px' : 0,
          position: 'fixed',
          bottom: 0,
          zIndex: 4,
          boxShadow: ios
            ? ''
            : `0px -1px 6px 5px ${theme.palette.background.default}`,
          background: ios
            ? 'rgba(54,54,54,0.8)'
            : theme.palette.background.paper,
          backdropFilter: 'blur(20px)',
          transition: leftOpen
            ? theme.transitions.create(['margin', 'width'], {
                easing: theme.transitions.easing.easeOut,
                duration: theme.transitions.duration.enteringScreen
              })
            : theme.transitions.create(['margin', 'width'], {
                easing: theme.transitions.easing.sharp,
                duration: theme.transitions.duration.leavingScreen
              })
        }}
        showLabels
        style={{ bottom: botHeight, color: '#a1998e' }}
      >
        {!(window.localStorage.getItem('guestmode') === 'activated') && (
          <BottomNavigationAction
            sx={{ minWidth: 50 }}
            component={Link}
            className="step-one"
            label={features.dashboard ? 'Dashboard' : 'Home'}
            value="/"
            to="/"
            icon={features.dashboard ? <Dashboard /> : <Home />}
          />
        )}
        <BottomNavigationAction
          label="Devices"
          value="/Devices"
          component={Link}
          to="/Devices"
          icon={<BladeIcon name="mdi:led-strip-variant" />}
          style={
            bottomBarOpen.indexOf('Devices') > -1
              ? { color: theme.palette.primary.main }
              : {}
          }
          // onContextMenu={(e: any) => {
          //   e.preventDefault();
          //   setBottomBarOpen('Devices');
          // }}
        />
        <BottomNavigationAction
          component={Link}
          to="/Scenes"
          label="Scenes"
          value="/Scenes"
          icon={<BladeIcon name="mdi:image" />}
          style={
            bottomBarOpen.indexOf('Scenes') > -1
              ? { color: theme.palette.primary.main }
              : {}
          }
          // onContextMenu={(e: any) => {
          //   e.preventDefault();
          //   setBottomBarOpen('Scenes');
          // }}
        />

        {features.integrations &&
          !(window.localStorage.getItem('guestmode') === 'activated') && (
            <BottomNavigationAction
              label="Integrations"
              value="/Integrations"
              component={Link}
              to="/Integrations"
              icon={<ElectricalServices />}
              style={
                bottomBarOpen.indexOf('Integrations') > -1
                  ? { color: theme.palette.primary.main }
                  : {}
              }
              // onContextMenu={(e: any) => {
              //   e.preventDefault();
              //   setBottomBarOpen('Integrations');
              // }}
            />
          )}

        {!(window.localStorage.getItem('guestmode') === 'activated') && (
          <BottomNavigationAction
            label="Settings"
            value="/Settings"
            icon={<Settings />}
            component={Link}
            to="/Settings"
            style={
              bottomBarOpen.indexOf('Settings') > -1
                ? { color: theme.palette.primary.main }
                : {}
            }
            // onContextMenu={(e: any) => {
            //   e.preventDefault();
            //   setBottomBarOpen('Settings');
            // }}
          />
        )}
      </BottomNavigation>
      {features.spotify && (
        <SpotifyFabFree
          spotifyEnabled={spotifyEnabled}
          setSpotifyEnabled={setSpotifyEnabled}
          spotifyExpanded={spotifyExpanded}
          setSpotifyExpanded={setSpotifyExpanded}
          spotifyURL={spotifyURL}
          setSpotifyURL={setSpotifyURL}
          botHeight={botHeight}
          setYoutubeEnabled={setYoutubeEnabled}
          setYoutubeExpanded={setYoutubeExpanded}
        />
      )}
      {integrations.spotify?.active && spAuthenticated && (
        <SpotifyFabPro
          spotifyEnabled={spotifyEnabled}
          setSpotifyEnabled={setSpotifyEnabled}
          spotifyExpanded={spotifyExpanded}
          setSpotifyExpanded={setSpotifyExpanded}
          spotifyURL={spotifyURL}
          setSpotifyURL={setSpotifyURL}
          botHeight={botHeight}
          setYoutubeEnabled={setYoutubeEnabled}
          setYoutubeExpanded={setYoutubeExpanded}
        />
      )}
      {features.youtube && (
        <YoutubeWidget
          youtubeEnabled={youtubeEnabled}
          setYoutubeEnabled={setYoutubeEnabled}
          youtubeExpanded={youtubeExpanded}
          setYoutubeExpanded={setYoutubeExpanded}
          youtubeURL={youtubeURL}
          setYoutubeURL={setYoutubeURL}
          botHeight={botHeight}
          setSpotifyEnabled={setSpotifyEnabled}
          setSpotifyExpanded={setSpotifyExpanded}
        />
      )}
      {features.scenemidi && <MIDIListener />}
      <AddSceneDialog />
      <AddDeviceDialog />
      <AddWledDialog />
      <AddVirtualDialog />
      <AddIntegrationDialog />
      <EditSceneDialog />
      {features.gamepad && (
        <>
          <Gamepad setScene={handleActivateScene} bottom={botHeight + 65} />
          <SmartBar
            open={smartBarPadOpen}
            setOpen={setSmartBarPadOpen}
            direct={false}
          />
        </>
      )}
      {!(window.localStorage.getItem('guestmode') === 'activated') && (
        <AddButton
          setBackdrop={setBackdrop}
          sx={{
            bottom: botHeight + 65,
            position: 'fixed',
            marginLeft: leftOpen ? `${drawerWidth / 2}px` : 0,
            left: '50%',
            transform: 'translateX(-50%)',
            transition: leftOpen
              ? theme.transitions.create(['margin'], {
                  easing: theme.transitions.easing.easeOut,
                  duration: theme.transitions.duration.enteringScreen
                })
              : theme.transitions.create(['margin'], {
                  easing: theme.transitions.easing.sharp,
                  duration: theme.transitions.duration.leavingScreen
                }),
            '&.MuiSpeedDial-directionUp, &.MuiSpeedDial-directionLeft': {
              bottom: theme.spacing(2) + 25
            },
            '& > button.MuiFab-primary': {
              backgroundColor: theme.palette.secondary.main
            },
            '& .MuiSpeedDialAction-staticTooltipLabel': {
              backgroundColor: 'transparent',
              marginLeft: '-1rem'
            }
          }}
          className="step-four"
        />
      )}
      <Backdrop
        style={{ zIndex: 1, backgroundColor: 'rgba(0, 0, 0, 0.8)' }}
        open={backdrop}
      />
    </>
  )
}
