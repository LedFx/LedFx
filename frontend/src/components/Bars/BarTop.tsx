/* eslint-disable react/destructuring-assignment */
import { useState, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  Menu as MenuIcon,
  MoreVert,
  Language,
  BarChart,
  GitHub,
  ChevronLeft,
  Login,
  Logout,
  Lan
} from '@mui/icons-material'
import isElectron from 'is-electron'
import {
  AppBar,
  Box,
  Badge,
  Toolbar,
  CircularProgress,
  Typography,
  IconButton,
  Menu,
  MenuItem,
  ListItemIcon,
  Button,
  useTheme
} from '@mui/material'
import { styled } from '@mui/styles'

import useStore from '../../store/useStore'
import { drawerWidth, ios } from '../../utils/helpers'
import TourDevice from '../Tours/TourDevice'
import TourScenes from '../Tours/TourScenes'
import TourSettings from '../Tours/TourSettings'
import TourDevices from '../Tours/TourDevices'
import TourIntegrations from '../Tours/TourIntegrations'
import BladeIcon from '../Icons/BladeIcon/BladeIcon'
import GlobalActionBar from '../GlobalActionBar'
import pkg from '../../../package.json'
import { Ledfx } from '../../api/ledfx'
import TourHome from '../Tours/TourHome'

export const StyledBadge = styled(Badge)(() => ({
  '& .MuiBadge-badge': {
    right: '45%',
    top: '115%',
    // border: `1px solid ${theme.palette.background.paper}`,
    padding: '0 4px',
    fontSize: 'x-small',
    height: '14px'
  }
}))

const LeftButtons = (
  pathname: any,
  history: any,
  open?: boolean,
  handleLeftBarOpen?: any
) => {
  const theme = useTheme()

  if (
    (pathname.split('/').length === 3 && pathname.split('/')[1] === 'device') ||
    pathname === '/Settings'
  ) {
    if (ios) {
      return (
        <IconButton size="large" color="inherit" onClick={() => history(-1)}>
          <ChevronLeft sx={{ fontSize: 32 }} />
        </IconButton>
      )
    }
    return (
      <Button
        size="large"
        variant="text"
        color="inherit"
        startIcon={<ChevronLeft />}
        onClick={() => history(-1)}
      >
        Back
      </Button>
    )
  }
  if (!open) {
    if (ios) {
      return (
        <Box
          style={{
            backgroundImage: 'url(/icon.png)',
            marginTop: 10,
            width: 32,
            height: 32,
            backgroundSize: 'contain'
          }}
          onClick={handleLeftBarOpen}
        />
      )
    }
    return (
      <IconButton
        color="inherit"
        aria-label="open drawer"
        onClick={handleLeftBarOpen}
        edge="start"
        sx={{ marginRight: theme.spacing(2), top: 8 }}
        className="step-three"
      >
        <MenuIcon />
      </IconButton>
    )
  }
  return null
}

const Title = (pathname: string, latestTag: string, virtuals: any) => {
  if (pathname === '/') {
    return (
      <>
        {`LedFx v${pkg.version}`}
        {latestTag !== `v${pkg.version}` ? (
          <Button
            color="error"
            variant="contained"
            onClick={() =>
              window.open(
                'https://github.com/YeonV/LedFx-Builds/releases/latest'
              )
            }
            sx={{ ml: 2 }}
          >
            New Update
          </Button>
        ) : null}
      </>
    )
  }
  if (pathname.split('/').length === 3 && pathname.split('/')[1] === 'device') {
    return virtuals[pathname.split('/')[2]]?.config.name
  }
  if (pathname === '/User') {
    return `LedFx Cloud ${
      localStorage.getItem('username') !== 'YeonV' ? 'Free' : ''
    } User`
  }
  return pathname.split('/').pop()
}

const TopBar = () => {
  // const classes = useStyles();
  const navigate = useNavigate()
  const theme = useTheme()

  const [loggingIn, setLogginIn] = useState(false)

  const open = useStore((state) => state.ui.bars && state.ui.bars?.leftBar.open)
  const latestTag = useStore((state) => state.ui.latestTag)
  const setLatestTag = useStore((state) => state.ui.setLatestTag)
  const setLeftBarOpen = useStore((state) => state.ui.setLeftBarOpen)
  // const darkMode = useStore((state) => state.ui.darkMode);
  // const setDarkMode = useStore((state) => state.ui.setDarkMode);
  const virtuals = useStore((state) => state.virtuals)
  const setDialogOpen = useStore((state) => state.setDialogOpen)
  const setHostManager = useStore((state) => state.setHostManager)
  const toggleGraphs = useStore((state) => state.toggleGraphs)
  const graphs = useStore((state) => state.graphs)
  // const config = useStore((state) => state.config);
  const isLogged = useStore((state) => state.isLogged)
  const setIsLogged = useStore((state) => state.setIsLogged)
  const disconnected = useStore((state) => state.disconnected)
  const setDisconnected = useStore((state) => state.setDisconnected)
  const { pathname } = useLocation()
  const history = useNavigate()
  const clearSnackbar = useStore((state) => state.ui.clearSnackbar)
  const features = useStore((state) => state.features)
  const platform = useStore((state) => state.platform)
  const [anchorEl, setAnchorEl] = useState<HTMLButtonElement | null>(null)
  const invDevice = useStore((state) => state.tours.device)
  const invSettings = useStore((state) => state.tours.settings)
  const invIntegrations = useStore((state) => state.tours.integrations)
  const invDevices = useStore((state) => state.tours.devices)
  const invScenes = useStore((state) => state.tours.scenes)
  const coreParams = useStore((state) => state.coreParams)
  const isCC = coreParams && Object.keys(coreParams).length > 0
  const updateNotificationInterval = useStore(
    (state) => state.updateNotificationInterval
  )
  const isCreator = localStorage.getItem('ledfx-cloud-role') === 'creator'
  const invisible = () => {
    switch (pathname.split('/')[1]) {
      case 'device':
        return invDevice
      case 'Scenes':
        return invScenes
      case 'Settings':
        return invSettings
      case 'Devices':
        return invDevices
      case 'Integrations':
        return invIntegrations
      default:
        return true
    }
  }

  const handleLeftBarOpen = () => {
    setLeftBarOpen(true)
  }
  const changeHost = () => {
    setDialogOpen(true, true)
    setAnchorEl(null)
  }
  const changeHostManager = () => {
    setHostManager(true)
    setAnchorEl(null)
  }
  // const toggleDarkMode = () => {
  //   setDarkMode(!darkMode);
  // };

  const changeGraphs = () => {
    toggleGraphs()
  }

  const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    setAnchorEl(event.currentTarget)
  }

  const logout = (e: React.MouseEvent<HTMLLIElement>) => {
    e.preventDefault()
    localStorage.removeItem('jwt')
    localStorage.removeItem('username')
    localStorage.removeItem('ledfx-cloud-userid')
    localStorage.removeItem('ledfx-cloud-role')
    setIsLogged(false)
  }

  useEffect(() => {
    setIsLogged(!!localStorage.getItem('jwt'))
  }, [pathname])

  useEffect(() => {
    if (latestTag !== `v${pkg.version}`) {
      if (
        Date.now() -
          parseInt(
            window.localStorage.getItem('last-update-notification') || '0',
            10
          ) >
        updateNotificationInterval * 1000 * 60
      ) {
        Ledfx('/api/notify', 'PUT', {
          title: 'Update available',
          text: 'A new version of LedFx has been released'
        })
        window.localStorage.setItem('last-update-notification', `${Date.now()}`)
      }
    }
  }, [updateNotificationInterval])

  useEffect(() => {
    const latest = async () => {
      const res = await fetch(
        'https://api.github.com/repos/YeonV/LedFx-Builds/releases/latest'
      )
      const resp = await res.json()
      return resp.tag_name as string
    }
    latest().then((r) => r !== latestTag && setLatestTag(r))
  }, [])

  useEffect(() => {
    const handleDisconnect = (e: any) => {
      if (e.detail) {
        setDisconnected(e.detail.isDisconnected)
        if (e.detail.isDisconnected === false) {
          window.localStorage.removeItem('undefined')
          setDialogOpen(false, true)
          clearSnackbar()
          if (window.localStorage.getItem('core-init') !== 'initialized') {
            window.localStorage.setItem('core-init', 'initialized')
          }
        }
      }
    }
    document.addEventListener('disconnected', handleDisconnect)
    return () => {
      document.removeEventListener('disconnected', handleDisconnect)
    }
  }, [])

  return (
    <>
      {isElectron() && platform !== 'darwin' && (
        <div className="titlebar">
          <div className="titlebarLogo" />
          LedFx
        </div>
      )}
      {!(
        isElectron() && window.localStorage.getItem('lock') === 'activated'
      ) && (
        <AppBar
          enableColorOnDark
          color="secondary"
          position="fixed"
          sx={{
            background: ios ? 'rgba(54,54,54,0.8)' : '',
            backdropFilter: ios ? 'blur(20px)' : '',
            color: ios ? '#fff' : '',
            paddingTop: isElectron() && platform !== 'darwin' ? '32px' : 0,
            zIndex: 10,
            transition: theme.transitions.create(['margin', 'width'], {
              easing: theme.transitions.easing.sharp,
              duration: theme.transitions.duration.leavingScreen
            }),
            ...(open && {
              width: `calc(100% - ${drawerWidth}px)`,
              marginLeft: `${drawerWidth}px`,
              transition: theme.transitions.create(['margin', 'width'], {
                easing: theme.transitions.easing.easeOut,
                duration: theme.transitions.duration.enteringScreen
              })
            })
          }}
        >
          <Toolbar
            style={{
              justifyContent: 'space-between',
              minHeight: 56
            }}
          >
            <div style={{ position: 'absolute', top: 0, left: 16 }}>
              {LeftButtons(pathname, history, open, handleLeftBarOpen)}
            </div>
            <Typography variant="h6" noWrap style={{ margin: '0 auto' }}>
              {Title(pathname, latestTag, virtuals)}
            </Typography>
            <div
              style={{
                display: 'flex',
                position: 'absolute',
                top: 4,
                right: 16
              }}
            >
              {disconnected ? (
                <Box>
                  <IconButton
                    aria-label="display more actions"
                    edge="end"
                    color="inherit"
                    onClick={changeHost}
                    className="step-two"
                    style={{ position: 'absolute', right: '4rem' }}
                  >
                    <BladeIcon
                      style={{ position: 'relative' }}
                      name="mdi:lan-disconnect"
                    />
                    <CircularProgress
                      size={44}
                      style={{
                        color: 'rgba(0,0,0,0.6)',
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        zIndex: 1
                      }}
                    />
                  </IconButton>
                </Box>
              ) : (
                <GlobalActionBar className="hideHd" />
              )}

              {!(window.localStorage.getItem('guestmode') === 'activated') && (
                <IconButton
                  aria-label="display more actions"
                  edge="end"
                  color="inherit"
                  onClick={handleClick}
                  className="step-two"
                  style={{ marginLeft: '1rem' }}
                >
                  <Badge variant="dot" color="error" invisible={invisible()}>
                    <MoreVert sx={{ fontSize: 32 }} />
                  </Badge>
                </IconButton>
              )}
            </div>

            {!(window.localStorage.getItem('guestmode') === 'activated') && (
              <Menu
                id="simple-menu"
                anchorEl={anchorEl}
                keepMounted
                open={Boolean(anchorEl)}
                onClose={() => setAnchorEl(null)}
                // className={classes.bladeMenu}
              >
                {features.cloud && isLogged && (
                  <MenuItem
                    divider
                    onClick={() => {
                      setAnchorEl(null)
                      navigate('/User')
                    }}
                  >
                    <ListItemIcon style={{ marginTop: -13 }}>
                      <StyledBadge
                        badgeContent={
                          localStorage.getItem('ledfx-cloud-role') ===
                          'authenticated'
                            ? 'logged in'
                            : localStorage.getItem('ledfx-cloud-role')
                        }
                        color="primary"
                      >
                        <GitHub />
                      </StyledBadge>
                    </ListItemIcon>
                    <div>
                      <div>{localStorage.getItem('username')}</div>
                    </div>
                  </MenuItem>
                )}
                <MenuItem onClick={changeHost}>
                  <ListItemIcon>
                    <Language />
                  </ListItemIcon>
                  Change Host
                </MenuItem>
                {isCC && isCreator && (
                  <MenuItem onClick={changeHostManager}>
                    <ListItemIcon>
                      <Lan />
                    </ListItemIcon>
                    Host Manager
                  </MenuItem>
                )}
                {/* <MenuItem onClick={toggleDarkMode}>
              <ListItemIcon>
                <Language />
              </ListItemIcon>
              Darkmode
            </MenuItem> */}
                <MenuItem onClick={changeGraphs}>
                  <ListItemIcon>
                    <BarChart color={graphs ? 'inherit' : 'secondary'} />
                  </ListItemIcon>
                  {!graphs ? 'Enable Graphs' : 'Disable Graphs'}
                </MenuItem>
                {pathname.split('/')[1] === 'device' ? (
                  <TourDevice cally={() => setAnchorEl(null)} />
                ) : pathname.split('/')[1] === 'Scenes' ? (
                  <TourScenes cally={() => setAnchorEl(null)} />
                ) : pathname.split('/')[1] === 'Settings' ? (
                  <TourSettings cally={() => setAnchorEl(null)} />
                ) : pathname.split('/')[1] === 'Devices' ? (
                  <TourDevices cally={() => setAnchorEl(null)} />
                ) : pathname.split('/')[1] === 'Integrations' ? (
                  <TourIntegrations cally={() => setAnchorEl(null)} />
                ) : (
                  <TourHome
                    variant="menuitem"
                    cally={() => setAnchorEl(null)}
                  />
                )}
                {/* <Doc type={'menuItem'} label={'Docs'} onClick={() => setAnchorEl(null)} /> */}

                {features.cloud && (
                  <MenuItem
                    onClick={(e: any) => {
                      e.preventDefault()
                      setLogginIn(true)
                      if (isLogged) {
                        setLogginIn(false)
                        logout(e)
                      } else if (
                        window.location.pathname.includes('hassio_ingress')
                      ) {
                        window.location.href = `https://strapi.yeonv.com/connect/github?callback=${window.location.origin}`
                      } else if (isElectron()) {
                        window.open(
                          'https://strapi.yeonv.com/connect/github?callback=ledfx://auth/github/',
                          '_blank',
                          'noopener,noreferrer'
                        )
                      } else {
                        window.open(
                          `https://strapi.yeonv.com/connect/github?callback=${window.location.origin}`,
                          '_blank',
                          'noopener,noreferrer'
                        )
                      }
                    }}
                  >
                    <ListItemIcon>
                      {isLogged ? (
                        <Logout />
                      ) : loggingIn ? (
                        <Box sx={{ display: 'flex', marginLeft: 0.6 }}>
                          <CircularProgress size="0.9rem" />
                        </Box>
                      ) : (
                        <Login />
                      )}
                    </ListItemIcon>
                    {isLogged ? 'Logout' : 'Login with Github'}
                  </MenuItem>
                )}
              </Menu>
            )}
          </Toolbar>
        </AppBar>
      )}
    </>
  )
}

export default TopBar
