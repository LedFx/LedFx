/* eslint-disable @typescript-eslint/indent */
/* eslint-disable no-console */
/* eslint-disable @typescript-eslint/no-unused-vars */
/* eslint-disable no-promise-executor-return */
/* eslint-disable no-plusplus */
/* eslint-disable no-await-in-loop */
import { useEffect, useState } from 'react'
import {
  Box,
  Typography,
  useTheme,
  Stack,
  CircularProgress as CircularProgress5,
  Fab,
  Tooltip,
  useMediaQuery
} from '@mui/material'
import { useNavigate } from 'react-router-dom'
import { DeleteForever, GitHub } from '@mui/icons-material'
import useStore from '../../store/useStore'
import { deleteFrontendConfig, sleep } from '../../utils/helpers'
import Gauge from './Gauge'
import BladeIcon from '../../components/Icons/BladeIcon/BladeIcon'
import Popover from '../../components/Popover/Popover'
import TourHome from '../../components/Tours/TourHome'
import SmartBar from '../../components/Dialogs/SmartBar'
import MGraph from '../../components/MGraph'
import openrgbLogo from '../../icons/png/openrgb.png'
import fx from '../../components/Icons/FX.svg'

const Dashboard = () => {
  const theme = useTheme()
  const db = true
  const navigate = useNavigate()
  const scanForDevices = useStore((state) => state.scanForDevices)
  const scanForOpenRgbDevices = useStore((state) => state.scanForOpenRgbDevices)
  const setIntro = useStore((state) => state.setIntro)

  const devices = useStore((state) => state.devices)
  const virtuals = useStore((state) => state.virtuals)
  const scenes = useStore((state) => state.scenes)
  const smallHeight = useMediaQuery(
    '(max-height: 680px) and (min-width: 480px)'
  )
  const xSmallHeight = useMediaQuery('(max-height: 580px)')

  const config = useStore((state) => state.config)
  const getDevices = useStore((state) => state.getDevices)
  const getVirtuals = useStore((state) => state.getVirtuals)

  const getScenes = useStore((state) => state.getScenes)
  const [scanning, setScanning] = useState(-1)

  const pixelTotal = Object.keys(devices)
    .map((d) => devices[d].config.pixel_count)
    .reduce((a, b) => a + b, 0)

  const devicesOnline = Object.keys(devices).filter((d) => devices[d].online)
  const virtualsReal = Object.keys(virtuals).filter(
    (d) => !virtuals[d].is_device
  )

  const pixelTotalOnline = Object.keys(devices)
    .map((d) => devices[d].online && devices[d].config.pixel_count)
    .reduce((a, b) => a + b, 0)

  const getSystemConfig = useStore((state) => state.getSystemConfig)
  const setSystemConfig = useStore((state) => state.setSystemConfig)

  const onSystemSettingsChange = (setting: string, value: any) => {
    setSystemConfig({ [setting]: value }).then(() => getSystemConfig())
  }
  const handleScan = () => {
    setScanning(0)
    scanForDevices()
      .then(async () => {
        for (let sec = 1; sec <= 30; sec++) {
          if (scanning === -1) break
          await sleep(1000).then(() => {
            getDevices()
            getVirtuals()
            if (scanning !== -1) setScanning(sec)
          })
        }
      })
      .then(() => {
        setScanning(-1)
      })
  }

  useEffect(() => {
    getScenes()
  }, [])

  return (
    <div className="Content">
      <Stack spacing={[0, 0, 2, 2, 2]} alignItems="center">
        {!xSmallHeight && (
          <>
            <Stack spacing={2} direction="row" className="hideTablet">
              <Gauge
                value={pixelTotal > 0 ? 100 : 0}
                unit="Pixels"
                total={pixelTotal}
                current={pixelTotal}
              />
              <Gauge
                value={Object.keys(devices).length > 0 ? 100 : 0}
                unit="Devices"
                total={Object.keys(devices).length}
                current={Object.keys(devices).length}
                onClick={() => navigate('/Devices')}
              />
              <Gauge
                value={virtualsReal.length > 0 ? 100 : 1}
                unit="Virtuals"
                total={Object.keys(virtuals).length}
                current={virtualsReal.length}
                onClick={() => navigate('/Devices')}
              />
              <Gauge
                unit="User Presets"
                total={
                  config.user_presets &&
                  Object.values(config.user_presets)?.length
                    ? Object.values(config.user_presets)
                        .map((e: any) => Object.keys(e).length)
                        .reduce((a: number, b: number) => a + b, 0)
                    : 0
                }
                current={
                  config.user_presets &&
                  Object.values(config.user_presets).length
                    ? Object.values(config.user_presets)
                        .map((e: any) => Object.keys(e).length)
                        .reduce((a: number, b: number) => a + b, 0)
                    : 0
                }
              />
            </Stack>
            <Stack spacing={2} direction="row" className="hideTablet">
              <Gauge
                unit="Pixels online"
                total={pixelTotal}
                current={pixelTotalOnline}
              />
              <Gauge
                unit="Devices online"
                total={Object.keys(devices).length}
                current={Object.keys(devicesOnline).length}
                onClick={() => navigate('/Devices')}
              />
              <Gauge
                unit="Scenes"
                total={Object.keys(scenes).length}
                current={Object.keys(scenes).length}
                onClick={() => navigate('/Scenes')}
              />
              <Gauge
                unit="User Colors"
                total={
                  ((config.user_colors &&
                    Object.keys(config.user_colors)?.length) ||
                    0) +
                  ((config.user_gradients &&
                    Object.keys(config.user_gradients)?.length) ||
                    0)
                }
                current={
                  ((config.user_colors &&
                    Object.keys(config.user_colors)?.length) ||
                    0) +
                  ((config.user_gradients &&
                    Object.keys(config.user_gradients)?.length) ||
                    0)
                }
              />
            </Stack>
          </>
        )}

        {db ? <SmartBar direct /> : <SmartBar direct />}
        <Stack spacing={2} direction={smallHeight ? 'row' : 'column'}>
          <Stack spacing={2} direction="row">
            <Tooltip title="Startup Assistant">
              <Fab
                aria-label="scan"
                onClick={() => {
                  setIntro(true)
                }}
                style={{
                  margin: '8px 0',
                  zIndex: 0
                }}
                sx={{
                  bgcolor: theme.palette.primary.main,
                  '&:hover': {
                    bgcolor: theme.palette.primary.light
                  }
                }}
              >
                <img
                  width={60}
                  height="auto"
                  src={fx}
                  alt="wled"
                  style={{ filter: 'grayscale(100%) brightness(0)' }}
                />
              </Fab>
            </Tooltip>
            <Tooltip
              title="Scan for WLED Devices"
              sx={{ '&': { marginLeft: '0 !important' } }}
            >
              <Box
                sx={{
                  m: 0,
                  position: 'relative',
                  zIndex: 0,
                  marginLeft: '8px !important'
                }}
              >
                <Popover
                  type="fab"
                  text="Create Segments?"
                  noIcon
                  onConfirm={() => {
                    onSystemSettingsChange('create_segments', true)
                    handleScan()
                  }}
                  onCancel={() => {
                    onSystemSettingsChange('create_segments', false)
                    handleScan()
                  }}
                >
                  {scanning > -1 ? (
                    <Typography
                      variant="caption"
                      style={{ fontSize: 10 }}
                      component="div"
                    >
                      {`${Math.round((scanning / 30) * 100)}%`}
                    </Typography>
                  ) : (
                    <BladeIcon name="wled" />
                  )}
                  {scanning > -1 && (
                    <CircularProgress5
                      size={68}
                      sx={{
                        color: theme.palette.primary.main,
                        position: 'absolute',
                        top: -6,
                        left: -6,
                        zIndex: 1
                      }}
                    />
                  )}
                </Popover>
              </Box>
            </Tooltip>
            <Tooltip title="Scan for OpenRGB Devices">
              <Fab
                aria-label="scan"
                onClick={() => {
                  scanForOpenRgbDevices()
                }}
                style={{
                  margin: '8px',
                  zIndex: 0
                }}
                sx={{
                  bgcolor: theme.palette.primary.main,
                  '&:hover': {
                    bgcolor: theme.palette.primary.light
                  }
                }}
              >
                <img
                  width={23}
                  height="auto"
                  src={openrgbLogo}
                  alt="wled"
                  style={{ filter: 'grayscale(100%) brightness(0)' }}
                />
              </Fab>
            </Tooltip>
            {/* <Tooltip title="Play / Pause LedFx Effect-streaming">
            <Fab
              aria-label="play-pause"
              onClick={() => {
                togglePause();
              }}
              style={{
                margin: '8px',
              }}
              sx={{
                bgcolor: theme.palette.primary.main,
                '&:hover': {
                  bgcolor: theme.palette.primary.light,
                },
              }}
            >
              {paused ? <PlayArrow /> : <PauseOutlined />}
            </Fab>
          </Tooltip> */}
            <Tooltip title="Clear Frontend Data">
              <span style={{ margin: 0, zIndex: 0 }}>
                <Popover
                  type="fab"
                  color="primary"
                  style={{ margin: '8px' }}
                  icon={<DeleteForever />}
                  text="Delete frontend data?"
                  onConfirm={() => {
                    deleteFrontendConfig()
                  }}
                />
              </span>
            </Tooltip>
            {/* <Tooltip title="SmartBar (CTRL+ALT+Y/Z)">
            <Fab
              aria-label="smartbar"
              onClick={() => setSmartBarOpen(true)}
              style={{
                margin: '8px',
              }}
              sx={{
                bgcolor: theme.palette.primary.main,
                '&:hover': {
                  bgcolor: theme.palette.primary.light,
                },
              }}
            >
              <Dvr />
            </Fab>
          </Tooltip> */}
            <Tooltip title="Guided Tour">
              <span style={{ margin: 0, zIndex: 0 }}>
                <TourHome className="step-one" variant="fab" />
              </span>
            </Tooltip>
          </Stack>
          <Stack spacing={2} direction="row" justifyContent="center">
            <Tooltip title="Github Core (python)">
              <Fab
                aria-label="github"
                onClick={() =>
                  window.open(
                    'https://github.com/LedFx/LedFx',
                    '_blank',
                    'noopener,noreferrer'
                  )
                }
                style={{
                  margin: '8px',
                  zIndex: 0
                }}
                sx={{
                  bgcolor: theme.palette.text.disabled,
                  '&:hover': {
                    bgcolor: theme.palette.primary.main
                  }
                }}
              >
                <GitHub />
              </Fab>
            </Tooltip>
            <Tooltip title="Github Client (react)">
              <Fab
                aria-label="github"
                onClick={() =>
                  window.open(
                    'https://github.com/YeonV/LedFx-Frontend-v2',
                    '_blank',
                    'noopener,noreferrer'
                  )
                }
                style={{
                  margin: '8px',
                  zIndex: 0
                }}
                sx={{
                  bgcolor: theme.palette.text.disabled,
                  '&:hover': {
                    bgcolor: theme.palette.primary.main
                  }
                }}
              >
                <GitHub />
              </Fab>
            </Tooltip>
            <Tooltip title="Discord">
              <Fab
                aria-label="discord"
                onClick={() =>
                  window.open(
                    'https://discord.gg/EZf8pAZ4',
                    '_blank',
                    'noopener,noreferrer'
                  )
                }
                style={{
                  margin: '8px',
                  zIndex: 0
                }}
                sx={{
                  bgcolor: theme.palette.text.disabled,
                  '&:hover': {
                    bgcolor: theme.palette.primary.main
                  }
                }}
              >
                <svg
                  role="img"
                  viewBox="-12 -12 48 48"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path d="M20.317 4.3698a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785-.037 19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01.0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.946 2.4189-2.1568 2.4189Z" />
                </svg>
              </Fab>
            </Tooltip>
          </Stack>
        </Stack>
      </Stack>
      {config.dev_mode && <MGraph />}
    </div>
  )
}

export default Dashboard
