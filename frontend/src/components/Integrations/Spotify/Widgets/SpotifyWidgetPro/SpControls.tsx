/* eslint-disable @typescript-eslint/indent */
import {
  Repeat,
  RepeatOne,
  Shuffle,
  SkipNext,
  SkipPrevious,
  VolumeDown,
  VolumeMute,
  VolumeUp,
  PauseCircle,
  PlayCircle
} from '@mui/icons-material'
import {
  Button,
  Box,
  IconButton,
  Slider,
  Select,
  MenuItem,
  Typography
} from '@mui/material'
import { useState, useContext } from 'react'
import useStore from '../../../../../store/useStore'
import useStyle, { TinyText, PosSliderStyles } from './SpWidgetPro.styles'
import { formatTime } from '../../../../../utils/helpers'
import {
  spotifyRepeat,
  spotifyShuffle,
  // spotifyPlay,
  spotifyPlayOnly
} from '../../../../../utils/spotifyProxies'
import SpSceneTrigger from './SpSceneTrigger'
import {
  SpStateContext,
  SpotifyControlContext,
  SpotifyStateContext,
  SpotifyTriggersContext,
  SpotifyVolumeContext
} from '../../SpotifyProvider'
import BladeIcon from '../../../../Icons/BladeIcon/BladeIcon'

export default function SpControls({ className }: any) {
  const classes = useStyle()
  const spotifyDevice = useStore((state) => state.spotify.spotifyDevice)
  const spotifyDevices = useStore((state) => state.spotify.spotifyDevices)

  const ctrlSpotify = useContext(SpotifyControlContext)
  const spotifyVolume = useContext(SpotifyVolumeContext)
  const triggers = useContext(SpotifyTriggersContext)
  const spotifyCtx = useContext(SpotifyStateContext)
  const spCtx = useContext(SpStateContext)
  const premium = !!spotifyCtx?.track_window?.current_track?.album?.name
  const hijack = premium || spCtx?.item?.album?.name || ''
  const [position, setPosition] = useState(-1)

  const duration = spotifyCtx?.duration || spCtx?.item?.duration_ms || 0
  const paused = spotifyCtx?.paused || spCtx?.is_playing || false
  const repeat_mode = spotifyCtx?.repeat_mode || 0
  const shuffle = spotifyCtx?.shuffle || false

  const { setVol, prev, togglePlay, next, setPos } = ctrlSpotify
  const marks = triggers?.map(({ position_ms, sceneName }) => ({
    value: position_ms,
    label: sceneName
  }))

  return (
    <Box
      className={`${classes.SpControlstyles} ${className}`}
      sx={{ width: '45%', margin: '0 auto' }}
    >
      {hijack === '' ? (
        <div>
          <Button onClick={() => spotifyPlayOnly(spotifyDevice)}>HiJack</Button>
        </div>
      ) : (
        <>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              mt: -1
            }}
          >
            <div className="showTablet">
              <IconButton
                aria-label="next song"
                sx={{ marginLeft: '0 !important' }}
                onClick={() => setVol(spotifyVolume === 0 ? 1 : 0)}
              >
                {spotifyVolume === 0 ? (
                  <VolumeMute
                    style={{ fontSize: '1.5rem' }}
                    htmlColor="rgba(255,255,255,0.7)"
                  />
                ) : spotifyVolume < 0.5 ? (
                  <VolumeDown
                    style={{ fontSize: '1.5rem' }}
                    htmlColor="rgba(255,255,255,0.7)"
                  />
                ) : (
                  <VolumeUp
                    style={{ fontSize: '1.5rem' }}
                    htmlColor="rgba(255,255,255,0.7)"
                  />
                )}
              </IconButton>
            </div>
            {premium && (
              <IconButton
                aria-label="shuffle"
                onClick={() => spotifyShuffle(spotifyDevice, !shuffle)}
              >
                {shuffle ? (
                  <Shuffle color="primary" />
                ) : (
                  <Shuffle htmlColor="#bbb" />
                )}
              </IconButton>
            )}
            {premium && (
              <IconButton aria-label="previous song" onClick={() => prev()}>
                <SkipPrevious fontSize="large" htmlColor="#bbb" />
              </IconButton>
            )}
            {premium && (
              <IconButton
                disabled={!premium}
                aria-label={paused ? 'play' : 'pause'}
                onClick={() => togglePlay()}
              >
                {paused ? (
                  <PlayCircle sx={{ fontSize: '3rem' }} htmlColor="#fff" />
                ) : (
                  <PauseCircle sx={{ fontSize: '3rem' }} htmlColor="#fff" />
                )}
              </IconButton>
            )}
            {premium && (
              <IconButton aria-label="next song" onClick={() => next()}>
                <SkipNext fontSize="large" htmlColor="#bbb" />
              </IconButton>
            )}
            {premium && (
              <IconButton
                aria-label="repeat"
                onClick={() => spotifyRepeat(spotifyDevice, repeat_mode)}
              >
                {repeat_mode === 0 ? (
                  <Repeat htmlColor="#bbb" />
                ) : repeat_mode === 1 ? (
                  <Repeat color="primary" />
                ) : (
                  <RepeatOne color="primary" />
                )}
              </IconButton>
            )}
            {!premium && (
              <Box textAlign="center">
                <Select
                  disabled
                  disableUnderline
                  defaultValue={
                    spotifyDevices && spotifyDevices.length > 0
                      ? spotifyDevices.find((d) => d.is_active)?.id
                      : undefined
                  }
                >
                  {spotifyDevices &&
                    spotifyDevices.length > 0 &&
                    spotifyDevices.map((d, i) => (
                      <MenuItem key={d.id + i} value={d.id}>
                        <div style={{ display: 'flex' }}>
                          <BladeIcon name={d.type} />
                          <Typography sx={{ marginLeft: 2 }}>
                            {d.name}
                          </Typography>
                        </div>
                      </MenuItem>
                    ))}
                </Select>
                <Typography color="InactiveCaptionText">
                  {paused ? 'Playing ' : 'Paused'}
                </Typography>
              </Box>
            )}
            <div className="showTablet">
              <SpSceneTrigger />
            </div>
          </Box>

          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}
          >
            <TinyText>
              {formatTime(spotifyCtx?.position || spCtx?.progress_ms || 0)}
            </TinyText>
            <Slider
              aria-label="time-indicator"
              size="small"
              marks={marks}
              value={
                position >= 0
                  ? position
                  : spotifyCtx?.position || spCtx?.progress_ms || 0
              }
              min={0}
              step={1}
              max={duration}
              onChange={(_, value) => {
                setPosition(value as number)
              }}
              onChangeCommitted={(_, value) => {
                setTimeout(() => setPosition(-1), 1000)
                setPos(value as number)
              }}
              sx={{ ...PosSliderStyles, margin: '0 10px' }}
            />
            <TinyText>{formatTime(duration)}</TinyText>
          </Box>
        </>
      )}
    </Box>
  )
}
