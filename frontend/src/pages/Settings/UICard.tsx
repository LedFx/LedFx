import { useEffect, useState } from 'react'
import { Input, Divider, Select, MenuItem } from '@mui/material'
import { SettingsSlider, SettingsRow } from './SettingsComponents'
import useStore from '../../store/useStore'
import useSliderStyles from '../../components/SchemaForm/components/Number/BladeSlider.styles'

const UICard = () => {
  const sliderClasses = useSliderStyles()

  const config = useStore((state) => state.config)
  const getSystemConfig = useStore((state) => state.getSystemConfig)
  const setSystemConfig = useStore((state) => state.setSystemConfig)
  const viewMode = useStore((state) => state.viewMode)
  const setViewMode = useStore((state) => state.setViewMode)
  const setFeatures = useStore((state) => state.setFeatures)
  const showFeatures = useStore((state) => state.showFeatures)
  const features = useStore((state) => state.features)
  const updateNotificationInterval = useStore(
    (state) => state.updateNotificationInterval
  )
  const setUpdateNotificationInterval = useStore(
    (state) => state.setUpdateNotificationInterval
  )

  const [fps, setFps] = useState(30)
  const [globalBrightness, setGlobalBrightness] = useState(100)
  const [pixelLength, setPixelLength] = useState(50)

  const setSystemSetting = (setting: string, value: any) => {
    setSystemConfig({ [setting]: value }).then(() => getSystemConfig())
  }

  useEffect(() => {
    if (typeof config.visualisation_fps === 'number') {
      setFps(config.visualisation_fps)
    }
    if (typeof config.visualisation_maxlen === 'number') {
      setPixelLength(config.visualisation_maxlen)
    }
  }, [config])

  useEffect(() => {
    getSystemConfig()
  }, [])

  const schemaTransmissionMode = useStore(
    (state) => state?.schemas?.core?.schema.properties.transmission_mode
  )

  return (
    <>
      <SettingsRow
        title={schemaTransmissionMode?.title}
        step="zero"
        value={fps}
      >
        <Select
          disableUnderline
          variant="standard"
          defaultValue={
            config.transmission_mode ||
            schemaTransmissionMode?.default ||
            'compressed'
          }
          onChange={(e) =>
            setSystemSetting('transmission_mode', e.target.value)
          }
        >
          {schemaTransmissionMode?.enum?.map((item: any) => (
            <MenuItem key={item} value={item}>
              {item}
            </MenuItem>
          ))}
        </Select>
      </SettingsRow>
      <SettingsRow title="Frontend FPS" step="two" value={fps}>
        <SettingsSlider
          value={fps}
          step={1}
          min={1}
          max={60}
          onChangeCommitted={(_e: any, val: any) =>
            setSystemSetting('visualisation_fps', val)
          }
          onChange={(_e: any, val: any) => {
            setFps(val)
          }}
        />
        <Input
          disableUnderline
          className={sliderClasses.input}
          style={{ width: 70 }}
          value={fps}
          margin="dense"
          onChange={(e) => {
            setFps(parseInt(e.target.value, 10))
          }}
          onBlur={(e) => {
            setSystemSetting('visualisation_fps', parseInt(e.target.value, 10))
          }}
          sx={{
            '& input': { textAlign: 'right' }
          }}
          inputProps={{
            min: 1,
            max: 60,
            type: 'number',
            'aria-labelledby': 'input-slider'
          }}
        />
      </SettingsRow>
      <SettingsRow title="Frontend Pixels" step="three" value={pixelLength}>
        <SettingsSlider
          value={pixelLength}
          step={1}
          valueLabelDisplay="auto"
          min={1}
          max={4096}
          marks={[{ value: 300, label: null }]}
          onChangeCommitted={(_e: any, val: any) =>
            setSystemSetting('visualisation_maxlen', val)
          }
          onChange={(_e: any, val: any) => {
            setPixelLength(val)
          }}
        />
        <Input
          disableUnderline
          className={sliderClasses.input}
          value={pixelLength}
          style={{ width: 70 }}
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
            max: 4096,
            type: 'number',
            'aria-labelledby': 'input-slider'
          }}
        />
      </SettingsRow>
      <SettingsRow
        title="Global Brightness"
        step="two"
        value={globalBrightness}
      >
        <SettingsSlider
          value={globalBrightness}
          step={1}
          min={0}
          max={100}
          onChangeCommitted={(_e: any, val: any) =>
            setSystemSetting('global_brightness', val / 100)
          }
          onChange={(_e: any, val: any) => {
            setGlobalBrightness(val)
          }}
        />
        <Input
          disableUnderline
          className={sliderClasses.input}
          style={{ width: 70 }}
          value={globalBrightness}
          margin="dense"
          onChange={(e) => {
            setGlobalBrightness(parseInt(e.target.value, 10))
          }}
          onBlur={(e) => {
            setSystemSetting('global_brightness', parseInt(e.target.value, 10))
          }}
          sx={{
            '& input': { textAlign: 'right' }
          }}
          inputProps={{
            min: 0,
            max: 100,
            type: 'number',
            'aria-labelledby': 'input-slider'
          }}
        />
      </SettingsRow>
      <SettingsRow
        title="Update Notification: wait min"
        value={updateNotificationInterval}
      >
        <SettingsSlider
          value={updateNotificationInterval}
          step={1}
          min={1}
          max={4320}
          onChange={(_e: any, val: number) =>
            setUpdateNotificationInterval(val)
          }
        />
        <Input
          disableUnderline
          className={sliderClasses.input}
          style={{ width: 70 }}
          value={updateNotificationInterval}
          margin="dense"
          onChange={(e) => {
            setUpdateNotificationInterval(parseInt(e.target.value, 10))
          }}
          sx={{
            '& input': { textAlign: 'right' }
          }}
          inputProps={{
            min: 1,
            max: 4320,
            type: 'number',
            'aria-labelledby': 'input-slider'
          }}
        />
      </SettingsRow>
      <Divider sx={{ m: '0.5rem 0 0.25rem 0' }} />
      <SettingsRow
        title="Expert Mode"
        direct
        checked={viewMode !== 'user'}
        onChange={() =>
          viewMode === 'user' ? setViewMode('expert') : setViewMode('user')
        }
      />
      {viewMode !== 'user' && (
        <SettingsRow
          title="Beta Mode"
          checked={features.beta}
          onChange={() => setFeatures('beta', !features.beta)}
        />
      )}
      {showFeatures.alpha && viewMode !== 'user' && (
        <SettingsRow
          title="Alpha Mode"
          checked={features.alpha}
          onChange={() => setFeatures('alpha', !features.alpha)}
        />
      )}
    </>
  )
}

export default UICard
