import { useEffect, useState } from 'react'
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Input
} from '@mui/material'
import useStore from '../../store/useStore'
import {
  SettingsRow
  // SettingsSlider
} from '../../pages/Settings/SettingsComponents'
import useSliderStyles from '../SchemaForm/components/Number/BladeSlider.styles'
// import { inverseLogScale, logScale } from '../../utils/helpers'

export default function FrontendPixelsTooSmall() {
  const sliderClasses = useSliderStyles()
  const fPixels = useStore((state) => state.config.visualisation_maxlen)
  const showMatrix = useStore((state) => state.showMatrix)
  const virtuals = useStore((state) => state.virtuals)
  const open = useStore((state) => state.dialogs.lessPixels?.open || false)
  const toggleShowMatrix = useStore((state) => state.toggleShowMatrix)
  const getSystemConfig = useStore((state) => state.getSystemConfig)
  const setSystemConfig = useStore((state) => state.setSystemConfig)
  const [pixelLength, setPixelLength] = useState(fPixels || 50)
  const [biggestDevice, setBiggestDevice] = useState({ id: '', pixels: 0 })

  const setDialogOpenLessPixels = useStore(
    (state) => state.setDialogOpenLessPixels
  )
  const setSystemSetting = (setting: string, value: any) => {
    setSystemConfig({ [setting]: value }).then(() => getSystemConfig())
    // .then(() => {
    //   setTimeout(() => {
    //     window.location.reload()
    //   }, 3000)
    // })
  }
  const handleClose = () => setDialogOpenLessPixels(false)

  useEffect(() => {
    const tooBig = Object.keys(virtuals).filter(
      (v: any) =>
        virtuals[v].config.rows > 1 && virtuals[v]?.pixel_count > fPixels
    )
    const biggest = tooBig.reduce(
      (a: any, b: any) =>
        virtuals[a]?.pixel_count > virtuals[b]?.pixel_count ? a : b,
      0
    )
    if (fPixels && showMatrix && tooBig.length > 0) {
      setBiggestDevice({ id: biggest, pixels: virtuals[biggest]?.pixel_count })
      setDialogOpenLessPixels(true)
    }
    if (fPixels && showMatrix && tooBig.length === 0) {
      setDialogOpenLessPixels(false)
    }
  }, [showMatrix, fPixels, virtuals, setDialogOpenLessPixels])

  useEffect(() => {
    getSystemConfig()
  }, [])

  useEffect(() => {
    getSystemConfig()
    setPixelLength(fPixels)
  }, [fPixels])

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      aria-labelledby="about-dialog-title"
      aria-describedby="about-dialog-description"
      PaperProps={{
        style: { margin: '0 auto' }
      }}
    >
      <DialogTitle id="about-dialog-title">Not enough Pixels</DialogTitle>
      <DialogContent sx={{ paddingBottom: '28px' }}>
        <DialogContentText id="about-dialog-description" marginBottom={3}>
          {fPixels >= biggestDevice.pixels
            ? 'All good now'
            : `${biggestDevice.id} has ${biggestDevice.pixels} pixels, but the Frontend
          is configured to show only ${fPixels} pixels. Please increase the
          number of pixels or disable the Matrix-Visualisation:`}
        </DialogContentText>
        <SettingsRow
          title="Show Matrix on Devices page (beta)"
          checked={showMatrix}
          onChange={() => toggleShowMatrix()}
          direct
        />
        <SettingsRow title="Frontend Pixels" step="three" value={pixelLength}>
          {/* <SettingsSlider
            value={Math.round(inverseLogScale(pixelLength))}
            step={1}
            valueLabelDisplay="auto"
            min={0} // Adjusted from 1 to 0
            max={14} // Log2(16384) = 14
            scale={(x: number) => logScale(x)}
            marks={[
              {
                value: Math.round(inverseLogScale(81)),
                label: Math.round(81).toString()
              },
              {
                value: Math.round(inverseLogScale(256)),
                label: Math.round(256).toString()
              },
              {
                value: Math.round(inverseLogScale(1024)),
                label: Math.round(1024).toString()
              },
              {
                value: Math.round(inverseLogScale(4096)),
                label: Math.round(4096).toString()
              },
              {
                value: Math.round(inverseLogScale(16384)),
                label: Math.round(16384).toString()
              }
            ]}
            onChangeCommitted={(_e: any, val: any) =>
              setSystemSetting(
                'visualisation_maxlen',
                Math.round(logScale(val))
              )
            }
            onChange={(_e: any, val: any) => {
              setPixelLength(Math.round(logScale(val)))
            }}
            valueLabelFormat={(val: number) => Math.round(val).toString()}
            sx={{
              marginTop: '28px'
            }}
          /> */}
          <Input
            disableUnderline
            className={sliderClasses.input}
            value={pixelLength}
            style={{ width: 100 }}
            margin="dense"
            onChange={(e) => {
              setPixelLength(parseInt(e.target.value, 10))
            }}
            onBlur={(e) =>
              setSystemSetting(
                'visualisation_maxlen',
                parseInt(e.target.value, 10)
              )
            }
            sx={{
              '& input': { textAlign: 'right' }
            }}
            inputProps={{
              min: 1,
              max: 16384,
              type: 'number',
              'aria-labelledby': 'input-slider'
            }}
          />
        </SettingsRow>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} autoFocus>
          OK
        </Button>
      </DialogActions>
    </Dialog>
  )
}
