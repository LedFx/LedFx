import { useContext, useEffect, useState } from 'react'
import Box from '@mui/material/Box'
import {
  InputAdornment,
  TextField,
  MenuItem,
  FormControl,
  InputLabel,
  Select
} from '@mui/material'
import useStore from '../../../../../store/useStore'

import Popover from '../../../../Popover/Popover'
import BladeIcon from '../../../../Icons/BladeIcon/BladeIcon'
import { SpStateContext, SpotifyStateContext } from '../../SpotifyProvider'

export default function SpSceneTrigger() {
  const spotifyState = useContext(SpotifyStateContext)
  const spCtx = useContext(SpStateContext)

  const scenes = useStore((state) => state.scenes)
  const getScenes = useStore((state) => state.getScenes)
  const [spotifyScene, setSpotifyScene] = useState(0)
  const player = useStore((state) => state.spotify.player)
  const spNetworkTime = useStore((state) => state.spotify.spNetworkTime)
  const setSpNetworkTime = useStore((state) => state.setSpNetworkTime)

  const addSpotifySongTrigger = useStore((state) => state.addSpSongTrigger)
  const getIntegrations = useStore((state) => state.getIntegrations)
  const songID =
    spotifyState?.track_window?.current_track?.id || spCtx?.item?.id || ''
  const songTitleAndArtist = `${
    spotifyState?.track_window?.current_track?.name || spCtx?.item?.name
  } - ${
    spotifyState?.track_window?.current_track?.artists[0]?.name ||
    spCtx?.item?.artists[0]?.name
  }`
  const spotifyTriggerData = {
    scene_id: spotifyScene, // Incorrectly sending scene_id instead of scene_id
    song_id: songID,
    song_name: songTitleAndArtist,
    song_position: spotifyState?.position || spCtx?.progress_ms || 0
  }

  const onConfirmHandler = (spotifyTriggerDataTemp: any) => {
    player.getCurrentState().then((state: any) => {
      if (!state) {
        // eslint-disable-next-line no-console
        console.error('User is not playing music through the Web Playback SDK')

        // return
      }
      const data = {
        ...spotifyTriggerDataTemp,
        ...{ song_position: state?.position || spCtx?.progress_ms || 0 }
      }
      addSpotifySongTrigger(data).then(() => getIntegrations())
    })
  }

  useEffect(() => {
    getScenes()
  }, [])

  return (
    <Popover
      variant="text"
      size="large"
      confirmDisabled={spotifyScene === 0}
      confirmContent="Set Now"
      icon={<BladeIcon name="mdi:timer-music-outline" />}
      onConfirm={() => onConfirmHandler(spotifyTriggerData)}
      content={
        <div>
          <Box sx={{ minWidth: 220, margin: 0, padding: '6px 5px 1px 5px' }}>
            <FormControl style={{ minWidth: 220 }}>
              <InputLabel
                id="scenelabel"
                style={{ marginLeft: 14, marginTop: -7 }}
              >
                Scene
              </InputLabel>
              <Select
                labelId="scenelabel"
                id="scene"
                value={spotifyScene}
                label="Scene"
                onChange={(_, v: any) => {
                  setSpotifyScene(v.props.value)
                }}
              >
                <MenuItem value={0}>select a scene</MenuItem>
                {scenes &&
                  Object.keys(scenes).length &&
                  Object.keys(scenes).map((s: any, i: number) => (
                    <MenuItem key={i} value={scenes[s].id || s}>
                      {scenes[s]?.name || s}
                    </MenuItem>
                  ))}
              </Select>
            </FormControl>
            <TextField
              label="Network Delay"
              style={{
                width: 150,
                color: '#fff',
                border: 0,
                marginLeft: 10
              }}
              InputProps={{
                endAdornment: <InputAdornment position="end">ms</InputAdornment>
              }}
              type="number"
              value={spNetworkTime}
              onChange={(e: any) => setSpNetworkTime(e.target.value)}
            />
          </Box>
        </div>
      }
    />
  )
}
