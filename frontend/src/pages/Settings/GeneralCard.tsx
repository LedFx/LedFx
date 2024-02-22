/* eslint-disable no-self-assign */
/* eslint-disable @typescript-eslint/indent */
import {
  CloudUpload,
  CloudDownload,
  PowerSettingsNew,
  Delete,
  Refresh,
  Info
} from '@mui/icons-material'
import isElectron from 'is-electron'
import { Divider } from '@mui/material'
import useStore from '../../store/useStore'
import { deleteFrontendConfig, download } from '../../utils/helpers'
import PopoverSure from '../../components/Popover/Popover'

import AboutDialog from '../../components/Dialogs/AboutDialog'
import { useStyles, SettingsButton, SettingsSwitch } from './SettingsComponents'

const GeneralCard = () => {
  const classes = useStyles()
  const getFullConfig = useStore((state) => state.getFullConfig)
  const deleteSystemConfig = useStore((state) => state.deleteSystemConfig)
  const importSystemConfig = useStore((state) => state.importSystemConfig)
  const shutdown = useStore((state) => state.shutdown)
  const restart = useStore((state) => state.restart)
  const disconnected = useStore((state) => state.disconnected)
  const settings = useStore((state) => state.config)
  const getSystemConfig = useStore((state) => state.getSystemConfig)
  const setSystemConfig = useStore((state) => state.setSystemConfig)

  const configDownload = async () => {
    getFullConfig().then((newConfig) =>
      download(newConfig, 'config.json', 'application/json')
    )
  }

  const configDelete = async () => {
    deleteFrontendConfig()
    deleteSystemConfig().then(() => {
      window.location.href = window.location.href
    })
  }

  const fileChanged = async (e: any) => {
    const fileReader = new FileReader()
    fileReader.readAsText(e.target.files[0], 'UTF-8')
    fileReader.onload = (ev: any) => {
      importSystemConfig(ev.target.result).then(() => {
        window.location.href = window.location.href
      })
    }
  }

  const onSystemSettingsChange = (setting: string, value: any) => {
    setSystemConfig({ [setting]: value }).then(() => getSystemConfig())
  }

  return (
    <div>
      <div
        className="step-settings-four"
        style={{ display: 'flex', justifyContent: 'space-between' }}
      >
        <div style={{ flex: '0 0 49%' }}>
          <SettingsButton
            startIcon={<CloudUpload />}
            onClick={() => configDownload()}
          >
            Export Config
          </SettingsButton>
          <PopoverSure
            startIcon={<Delete />}
            label="Reset Config"
            variant="outlined"
            color="inherit"
            className={classes.actionButton}
            onConfirm={() => configDelete()}
            vertical="top"
            wrapperStyle={{
              marginTop: '0.5rem',
              flexBasis: '49%'
            }}
          />
          <input
            hidden
            accept="application/json"
            id="contained-button-file"
            type="file"
            onChange={(e) => fileChanged(e)}
          />
          <label
            htmlFor="contained-button-file"
            style={{ width: '100%', flexBasis: '49%' }}
          >
            <SettingsButton component="span" startIcon={<CloudDownload />}>
              Import Config
            </SettingsButton>
          </label>
          {isElectron() &&
            window.process?.argv.indexOf('integratedCore') !== -1 && (
              <SettingsButton
                startIcon={<CloudUpload />}
                onClick={() =>
                  (window as any).api.send('toMain', { command: 'open-config' })
                }
              >
                Config Location
              </SettingsButton>
            )}
        </div>
        <div style={{ flex: '0 0 49%' }}>
          <AboutDialog startIcon={<Info />} className={classes.actionButton}>
            About
          </AboutDialog>
          <SettingsButton
            disabled={disconnected}
            startIcon={<Refresh />}
            onClick={restart}
          >
            {isElectron() &&
            window.process?.argv.indexOf('integratedCore') !== -1
              ? 'Restart Core'
              : 'Restart'}
          </SettingsButton>

          <SettingsButton
            disabled={disconnected}
            startIcon={<PowerSettingsNew />}
            onClick={shutdown}
          >
            {isElectron() &&
            window.process?.argv.indexOf('integratedCore') !== -1
              ? 'Shutdown Core'
              : 'Shutdown'}
          </SettingsButton>
          {isElectron() &&
            window.process?.argv.indexOf('integratedCore') !== -1 && (
              <SettingsButton
                startIcon={<PowerSettingsNew />}
                onClick={() => {
                  ;(window as any).api.send('toMain', { command: 'start-core' })
                }}
              >
                Start Core
              </SettingsButton>
            )}
        </div>
      </div>
      <Divider style={{ margin: '20px 0 10px' }} />
      <div
        className={`${classes.settingsRow} step-settings-six `}
        style={{ flexBasis: '100%' }}
      >
        <label>Global Transitions</label>
        <SettingsSwitch
          checked={settings.global_transitions}
          onChange={() =>
            onSystemSettingsChange(
              'global_transitions',
              !settings.global_transitions
            )
          }
        />
      </div>
      <div
        className={`${classes.settingsRow} step-settings-seven `}
        style={{ flexBasis: '100%' }}
      >
        <label>Scan on startup</label>
        <SettingsSwitch
          checked={settings.scan_on_startup}
          onChange={() =>
            onSystemSettingsChange('scan_on_startup', !settings.scan_on_startup)
          }
        />
      </div>
      <div
        className={`${classes.settingsRow} step-settings-eight `}
        style={{ flexBasis: '100%' }}
      >
        <label>Auto-generate Virtuals for Segments</label>
        <SettingsSwitch
          checked={settings.create_segments}
          onChange={() =>
            onSystemSettingsChange('create_segments', !settings.create_segments)
          }
        />
      </div>
    </div>
  )
}

export default GeneralCard
