import React, { useContext } from 'react'
import {
  ListItemIcon,
  Typography,
  Toolbar,
  AppBar,
  Dialog,
  Button,
  Grid,
  useTheme
} from '@mui/material'
import { Settings, NavigateBefore } from '@mui/icons-material'
import isElectron from 'is-electron'
import {
  MuiMenuItem,
  SpotifyScreenDefaultProps,
  SpotifyScreenProps,
  Transition
} from './SpotifyScreen.props'
import useEditVirtualsStyles from '../../../Devices/EditVirtuals/EditVirtuals.styles'
import SpotifyWidgetPro from '../../../../components/Integrations/Spotify/Widgets/SpotifyWidgetPro/SpWidgetPro'
// import RadarChart from '../../../../components/Integrations/Spotify/Widgets/SpotifyWidgetPro/SpAudioFeatures/SpRadarChart';
import SpAudioFeatures from '../../../../components/Integrations/Spotify/Widgets/SpotifyWidgetPro/SpAudioFeatures/SpAudioFeatures'
import SpotifyTriggerTable from '../../../../components/Integrations/Spotify/Widgets/SpotifyWidgetPro/SpTriggerTable'
import SpPlaylist from '../../../../components/Integrations/Spotify/Widgets/SpotifyWidgetPro/SpPlaylist'
import { SpotifyStateContext } from '../../../../components/Integrations/Spotify/SpotifyProvider'

export default function SpotifyScreen({
  icon = <Settings />,
  startIcon,
  label = '',
  type,
  className,
  color = 'primary',
  variant = 'contained',
  innerKey,
  disabled = false,
  size = 'small'
}: SpotifyScreenProps) {
  const classes = useEditVirtualsStyles()
  const theme = useTheme()
  const [open, setOpen] = React.useState(false)
  const spotifyCtx = useContext(SpotifyStateContext)
  const premium = spotifyCtx?.track_window?.current_track?.album.name
  const handleClickOpen = () => {
    setOpen(true)
  }

  const handleClose = () => {
    setOpen(false)
  }

  return (
    <>
      {type === 'menuItem' ? (
        <MuiMenuItem
          key={innerKey}
          className={className}
          onClick={(e: any) => {
            e.preventDefault()
            handleClickOpen()
          }}
        >
          <ListItemIcon>{icon}</ListItemIcon>
          {label}
        </MuiMenuItem>
      ) : (
        <Button
          variant={variant}
          startIcon={startIcon}
          color={color}
          onClick={() => {
            handleClickOpen()
          }}
          size={size}
          disabled={disabled}
          className={className}
        >
          {label}
          {!startIcon && icon}
        </Button>
      )}
      <Dialog
        fullScreen
        open={open}
        onClose={handleClose}
        TransitionComponent={Transition}
        PaperProps={{
          style: {
            backgroundColor: theme.palette.background.default
          }
        }}
      >
        <AppBar enableColorOnDark className={classes.appBar}>
          <Toolbar>
            <Button
              autoFocus
              color="primary"
              variant="contained"
              startIcon={<NavigateBefore />}
              onClick={handleClose}
              style={{ marginRight: '1rem' }}
            >
              back
            </Button>
            <Typography variant="h6" className={classes.title}>
              Spotify
            </Typography>
          </Toolbar>
        </AppBar>
        <div style={{ margin: '1rem' }}>
          <SpotifyWidgetPro />
          <div style={{ marginTop: '1rem' }} />
          <Grid xl={12} container item alignItems="center" spacing={1}>
            {premium && !isElectron() && <SpAudioFeatures />}
            <SpPlaylist />
          </Grid>
          <div style={{ marginTop: '1rem' }} />
          <SpotifyTriggerTable />
        </div>
        {/* <SpotifyWidgetSmall  />
        <div style={{ marginTop: '2rem' }} />
        <SpotifyWidgetDev  /> */}
      </Dialog>
    </>
  )
}

SpotifyScreen.defaultProps = SpotifyScreenDefaultProps
