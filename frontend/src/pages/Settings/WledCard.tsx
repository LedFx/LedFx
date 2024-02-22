import { useEffect } from 'react'
import { styled } from '@mui/material/styles'
import {
  Card,
  CardHeader,
  CardContent,
  InputLabel,
  MenuItem,
  FormControl,
  Checkbox,
  Icon,
  TextField,
  Select,
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Typography
} from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import Wled from '../../components/Icons/Wled'
import useStore from '../../store/useStore'

const PREFIX = 'WledCard'

const classes = {
  content: `${PREFIX}-content`,
  rowContainer: `${PREFIX}-rowContainer`,
  rowB: `${PREFIX}-rowB`,
  row: `${PREFIX}-row`,
  formControl: `${PREFIX}-formControl`,
  check: `${PREFIX}-check`
}

const StyledCard = styled(Card)({
  [`& .${classes.content}`]: {
    display: 'flex',
    flexDirection: 'column'
  },
  [`& .${classes.rowContainer}`]: {
    border: '1px solid',
    borderRadius: '4px'
  },
  [`& .${classes.rowB}`]: {
    display: 'flex',
    flexDirection: 'row'
  },
  [`& .${classes.row}`]: {
    display: 'flex',
    flexDirection: 'row',
    padding: '10px 5px',
    '&:not(:last-child)': {
      borderBottom: '1px solid'
    }
  },
  [`& .${classes.formControl}`]: {
    width: '100%',
    marginRight: '1rem'
  },
  [`& .${classes.check}`]: {
    '& .MuiSvgIcon-root': {
      width: '2rem',
      height: '2rem'
    }
  }
})

const WledCard = ({ className }: any) => {
  const setSystemConfig = useStore((state) => state.setSystemConfig)
  const getSystemConfig = useStore((state) => state.getSystemConfig)
  const settings = useStore((state) => state.config)

  const toggleSetting = (setting: string, value: any) => {
    setSystemConfig({
      wled_preferences: { [setting]: { user_enabled: value } }
    }).then(() => getSystemConfig())
  }
  const onChangeSetting = (setting: string, value: any) => {
    setSystemConfig({
      wled_preferences: { [setting]: { setting: value } }
    }).then(() => getSystemConfig())
  }
  const onScanOnStart = (setting: string, value: any) => {
    setSystemConfig({ [setting]: value }).then(() => getSystemConfig())
  }

  useEffect(() => {
    getSystemConfig()
  }, [getSystemConfig])

  return settings.wled_preferences ? (
    <StyledCard style={{ marginBottom: '2rem' }} className={className}>
      <CardHeader
        title="WLED Integration"
        subheader="Configure WLED-Settings"
        action={
          <Icon
            style={{
              margin: '1rem',
              fontSize: '2.5rem'
            }}
          >
            <Wled />
          </Icon>
        }
      />
      <CardContent className={classes.content}>
        <FormControl>
          <InputLabel id="wled-scan-selector">
            Scan for WLED on startup
          </InputLabel>
          <Select
            labelId="wled-scan-selector"
            id="wled-scan-select"
            value={settings.scan_on_startup}
            onChange={(e) => onScanOnStart('scan_on_startup', e.target.value)}
          >
            <MenuItem value="true">Yes</MenuItem>
            <MenuItem>No</MenuItem>
          </Select>
        </FormControl>
        <Accordion style={{ marginTop: '2rem' }}>
          <AccordionSummary
            expandIcon={<ExpandMoreIcon />}
            aria-controls="panel1bh-content"
            id="panel1bh-header"
          >
            <Typography>WLED Sync-Settings</Typography>
          </AccordionSummary>
          <AccordionDetails className={classes.content}>
            <p style={{ margin: '0 0 2rem 0' }}>
              LedFx can configure WLED&apos;s sync settings to recommended
              values.
              <br />
              <br />
              WARNING: <br />
              If you are using your strips with other controllers, changes to
              these settings might impact their functionality!
              <br />
              <br />
              LedFx will only change settings that you select with the checkbox
            </p>
            <div className={classes.rowContainer}>
              <div className={classes.row}>
                <Checkbox
                  checked={
                    settings.wled_preferences.wled_preferred_mode.user_enabled
                  }
                  className={classes.check}
                  onChange={() =>
                    toggleSetting(
                      'wled_preferred_mode',
                      !settings.wled_preferences.wled_preferred_mode
                        .user_enabled
                    )
                  }
                  inputProps={{ 'aria-label': 'primary checkbox' }}
                />
                <FormControl className={classes.formControl}>
                  <InputLabel id="wled-mode-selector">
                    Preferred WLED mode
                  </InputLabel>
                  <Select
                    labelId="wled-mode-selector"
                    id="wled-mode-select"
                    value={
                      settings.wled_preferences.wled_preferred_mode.setting
                    }
                    onChange={(e) =>
                      onChangeSetting('wled_preferred_mode', e.target.value)
                    }
                    disabled={
                      !settings.wled_preferences.wled_preferred_mode
                        .user_enabled
                    }
                  >
                    <MenuItem value="unset">Unset</MenuItem>
                    <MenuItem value="E131">E131</MenuItem>
                    <MenuItem value="DDP">DDP</MenuItem>
                    <MenuItem value="UDP">UDP</MenuItem>
                  </Select>
                </FormControl>
              </div>
              <div className={classes.row}>
                <Checkbox
                  checked={
                    settings.wled_preferences.realtime_gamma_enabled
                      .user_enabled
                  }
                  className={classes.check}
                  onChange={() =>
                    toggleSetting(
                      'realtime_gamma_enabled',
                      !settings.wled_preferences.realtime_gamma_enabled
                        .user_enabled
                    )
                  }
                  inputProps={{ 'aria-label': 'primary checkbox' }}
                />
                <FormControl className={classes.formControl}>
                  <InputLabel id="wled-gamma">Realtime Gamma</InputLabel>
                  <Select
                    labelId="wled-gamma"
                    id="wled-gamma-select"
                    value={
                      settings.wled_preferences.realtime_gamma_enabled.setting
                    }
                    onChange={(e) =>
                      onChangeSetting('realtime_gamma_enabled', e.target.value)
                    }
                    disabled={
                      !settings.wled_preferences.realtime_gamma_enabled
                        .user_enabled
                    }
                  >
                    <MenuItem value="true">Enable</MenuItem>
                    <MenuItem>Disable</MenuItem>
                  </Select>
                </FormControl>
              </div>
              <div className={classes.row}>
                <Checkbox
                  checked={
                    settings.wled_preferences.force_max_brightness.user_enabled
                  }
                  className={classes.check}
                  onChange={() =>
                    toggleSetting(
                      'force_max_brightness',
                      !settings.wled_preferences.force_max_brightness
                        .user_enabled
                    )
                  }
                  inputProps={{ 'aria-label': 'primary checkbox' }}
                />
                <FormControl className={classes.formControl}>
                  <InputLabel id="wled-brightness">
                    Force MaxBrightness
                  </InputLabel>
                  <Select
                    labelId="wled-brightness"
                    id="wled-brightness-select"
                    value={
                      settings.wled_preferences.force_max_brightness.setting
                    }
                    onChange={(e) =>
                      onChangeSetting('force_max_brightness', e.target.value)
                    }
                    disabled={
                      !settings.wled_preferences.force_max_brightness
                        .user_enabled
                    }
                  >
                    <MenuItem value="true">Enable</MenuItem>
                    <MenuItem>Disable</MenuItem>
                  </Select>
                </FormControl>
              </div>
              <div className={classes.row}>
                <Checkbox
                  checked={
                    settings.wled_preferences.realtime_dmx_mode.user_enabled
                  }
                  className={classes.check}
                  onChange={() =>
                    toggleSetting(
                      'realtime_dmx_mode',
                      !settings.wled_preferences.realtime_dmx_mode.user_enabled
                    )
                  }
                  inputProps={{ 'aria-label': 'primary checkbox' }}
                />
                <FormControl className={classes.formControl}>
                  <InputLabel id="wled-dmx">DMX mode</InputLabel>
                  <Select
                    labelId="wled-dmx"
                    id="wled-dmx-select"
                    value={settings.wled_preferences.realtime_dmx_mode.setting}
                    onChange={(e) =>
                      onChangeSetting('realtime_dmx_mode', e.target.value)
                    }
                    disabled={
                      !settings.wled_preferences.realtime_dmx_mode.user_enabled
                    }
                  >
                    <MenuItem value="MultiRGB">Disabled</MenuItem>
                    <MenuItem value="MultiRGB">Single RGB</MenuItem>
                    <MenuItem value="MultiRGB">Single DRGB</MenuItem>
                    <MenuItem value="MultiRGB">Multi RGB</MenuItem>
                    <MenuItem value="MultiRGB">Dimmer + Multi RGB</MenuItem>
                    <MenuItem value="MultiRGB">Multi RGBW</MenuItem>
                  </Select>
                </FormControl>
              </div>
              <div className={classes.row}>
                <Checkbox
                  checked={
                    settings.wled_preferences.start_universe_setting
                      .user_enabled
                  }
                  className={classes.check}
                  onChange={() =>
                    toggleSetting(
                      'start_universe_setting',
                      !settings.wled_preferences.start_universe_setting
                        .user_enabled
                    )
                  }
                  inputProps={{ 'aria-label': 'primary checkbox' }}
                />
                <TextField
                  type="number"
                  label="Start universe"
                  id="wled-universe-select"
                  value={
                    settings.wled_preferences.start_universe_setting.setting
                  }
                  onChange={(e) =>
                    onChangeSetting('start_universe_setting', e.target.value)
                  }
                  disabled={
                    !settings.wled_preferences.start_universe_setting
                      .user_enabled
                  }
                  className={classes.formControl}
                />
              </div>
              <div className={classes.row}>
                <Checkbox
                  checked={
                    settings.wled_preferences.dmx_address_start.user_enabled
                  }
                  className={classes.check}
                  onChange={() =>
                    toggleSetting(
                      'dmx_address_start',
                      !settings.wled_preferences.dmx_address_start.user_enabled
                    )
                  }
                  inputProps={{ 'aria-label': 'primary checkbox' }}
                />
                <TextField
                  type="number"
                  label="DMX start address"
                  id="wled-dmx-start-select"
                  value={settings.wled_preferences.dmx_address_start.setting}
                  onChange={(e) =>
                    onChangeSetting('dmx_address_start', e.target.value)
                  }
                  disabled={
                    !settings.wled_preferences.dmx_address_start.user_enabled
                  }
                  className={classes.formControl}
                />
              </div>
              <div className={classes.row}>
                <Checkbox
                  checked={
                    settings.wled_preferences.inactivity_timeout.user_enabled
                  }
                  className={classes.check}
                  onChange={() =>
                    toggleSetting(
                      'inactivity_timeout',
                      !settings.wled_preferences.inactivity_timeout.user_enabled
                    )
                  }
                  inputProps={{ 'aria-label': 'primary checkbox' }}
                />
                <TextField
                  type="number"
                  label="Inactivity Timeout"
                  id="wled-inactivity-select"
                  value={settings.wled_preferences.inactivity_timeout.setting}
                  onChange={(e) =>
                    onChangeSetting('inactivity_timeout', e.target.value)
                  }
                  disabled={
                    !settings.wled_preferences.inactivity_timeout.user_enabled
                  }
                  className={classes.formControl}
                />
              </div>
            </div>
          </AccordionDetails>
        </Accordion>
      </CardContent>
    </StyledCard>
  ) : null
}

export default WledCard
