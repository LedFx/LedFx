/* eslint-disable no-await-in-loop */
/* eslint-disable no-plusplus */
import { useTheme, Stack, Box, Button } from '@mui/material'
import { useState } from 'react'
import BladeFrame from '../../components/SchemaForm/components/BladeFrame'
import DbButton from './DbButton'
import GlobalActionBar from '../../components/GlobalActionBar'
import useStore from '../../store/useStore'
import { deleteFrontendConfig, sleep } from '../../utils/helpers'
import Popover from '../../components/Popover/Popover'
import BladeIcon from '../../components/Icons/BladeIcon/BladeIcon'
import openrgbLogo from '../../icons/png/openrgb.png'
import fx from '../../components/Icons/FX.svg'

const DbGlobalActions = () => {
  const theme = useTheme()
  const [scanning, setScanning] = useState(-1)
  const paused = useStore((state) => state.paused)
  const togglePause = useStore((state) => state.togglePause)
  const scanForDevices = useStore((state) => state.scanForDevices)
  const getDevices = useStore((state) => state.getDevices)
  const getVirtuals = useStore((state) => state.getVirtuals)
  const getSystemConfig = useStore((state) => state.getSystemConfig)
  const setSystemConfig = useStore((state) => state.setSystemConfig)
  const scanForOpenRgbDevices = useStore((state) => state.scanForOpenRgbDevices)
  const setIntro = useStore((state) => state.setIntro)

  const onSystemSettingsChange = (setting: string, value: any) => {
    setSystemConfig({ [setting]: value }).then(() => getSystemConfig())
  }

  const handleScan = () => {
    setScanning(0)
    scanForDevices()
      .then(async () => {
        for (let sec = 1; sec <= 30; sec++) {
          await sleep(1000).then(() => {
            getDevices()
            getVirtuals()
            setScanning(sec)
          })
        }
      })
      .then(() => {
        setScanning(-1)
      })
  }

  return (
    <BladeFrame
      labelStyle={{
        background: theme.palette.background.default,
        color: theme.palette.primary.main
      }}
      style={{ borderColor: theme.palette.primary.main, paddingLeft: 10 }}
      title="Global Actions"
    >
      <Stack width="100%">
        <GlobalActionBar type="indicator" />
        <div style={{ height: 10 }} />
        <DbButton
          onClick={() => togglePause()}
          icon={paused ? 'PlayArrow' : 'PauseOutlined'}
          text="Play"
        />
        <Button
          color="inherit"
          variant="text"
          aria-label="scan"
          onClick={() => {
            setIntro(true)
          }}
          style={{ padding: '11px', marginLeft: '0rem', flex: 1 }}
        >
          <Box
            sx={{
              fontSize: '0.8125rem',
              lineHeight: '1.75',
              width: '100%',
              display: 'flex',
              textTransform: 'none',
              alignItems: 'center',
              '& .MuiButton-startIcon': {
                mr: 3
              }
            }}
          >
            <img
              width={50}
              height="30px"
              src={fx}
              alt="wled"
              style={{
                filter: 'invert(1) brightness(2)',
                objectFit: 'cover',
                marginRight: 8,
                marginLeft: -8
              }}
            />
            Startup Assistant
          </Box>
        </Button>
        <Button
          color="inherit"
          variant="text"
          aria-label="scan"
          onClick={() => {
            scanForOpenRgbDevices()
          }}
          style={{ padding: '11px', marginLeft: '0rem', flex: 1 }}
        >
          <Box
            sx={{
              fontSize: '0.8125rem',
              lineHeight: '1.75',
              width: '100%',
              display: 'flex',
              textTransform: 'none',
              alignItems: 'center',
              '& .MuiButton-startIcon': {
                mr: 3
              }
            }}
          >
            <img
              width={24}
              height="auto"
              src={openrgbLogo}
              alt="wled"
              style={{
                filter: 'grayscale(100%) brightness(0) invert(1) brightness(2)',
                marginRight: 22,
                marginLeft: 4
              }}
            />
            Scan for OpenRGB devices
          </Box>
        </Button>
        <Popover
          noIcon
          variant="text"
          color="inherit"
          style={{ padding: '11px', marginLeft: '0rem', flex: 1 }}
          wrapperStyle={{ display: 'flex' }}
          onConfirm={() => {
            onSystemSettingsChange('create_segments', true)
            handleScan()
          }}
          onCancel={() => {
            onSystemSettingsChange('create_segments', false)
            handleScan()
          }}
          text="Import Segments?"
        >
          <Box
            sx={{
              fontSize: 16,
              width: '100%',
              display: 'flex',
              textTransform: 'none',
              alignItems: 'center',
              '& .MuiButton-startIcon': {
                mr: 3
              }
            }}
          >
            <BladeIcon
              name="wled"
              style={{
                marginTop: -4,
                marginRight: 23,
                marginLeft: 4
              }}
            />
            <span style={{ fontSize: '0.8125rem', lineHeight: '1.75' }}>
              {scanning > -1
                ? `Scanning ${Math.round((scanning / 30) * 100)}%`
                : 'Scan for WLED devices'}
            </span>
          </Box>
        </Popover>
        <DbButton
          onClick={() => deleteFrontendConfig()}
          icon="Delete"
          text="Delete Client Data"
        />
      </Stack>
    </BladeFrame>
  )
}

export default DbGlobalActions
