import { useContext, useState } from 'react'
import Slider from '@mui/material/Slider'
import IconButton from '@mui/material/IconButton'
import Stack from '@mui/material/Stack'
import { VolumeDown, VolumeMute, VolumeUp } from '@mui/icons-material'
import { VolSliderStyles } from './SpWidgetPro.styles'
import {
  SpotifyControlContext,
  SpotifyVolumeContext
} from '../../SpotifyProvider'

export default function SpVolume() {
  const [volu, setVolu] = useState(-1)
  const spotifyVolume = useContext(SpotifyVolumeContext)
  const { setVol } = useContext(SpotifyControlContext)
  return (
    <Stack
      spacing={2}
      direction="row"
      sx={{ width: '80%' }}
      alignItems="center"
    >
      <IconButton
        aria-label="next song"
        sx={{ marginLeft: '0 !important' }}
        onClick={() => setVol(spotifyVolume === 0 ? 1 : 0)}
      >
        {spotifyVolume === 0 ? (
          <VolumeMute htmlColor="rgba(255,255,255,0.4)" />
        ) : spotifyVolume < 0.5 ? (
          <VolumeDown htmlColor="rgba(255,255,255,0.4)" />
        ) : (
          <VolumeUp htmlColor="rgba(255,255,255,0.4)" />
        )}
      </IconButton>
      <Slider
        aria-label="Volume"
        min={0}
        max={100}
        value={volu > 0 ? volu : spotifyVolume * 100}
        onChange={(_, v) => setVolu((v as number) / 100)}
        onChangeCommitted={(e, v: any) => {
          setVol(v / 100)
          setVolu(-1)
        }}
        sx={{ ...VolSliderStyles, '&&&': { marginLeft: 0, marginRight: 3 } }}
      />
    </Stack>
  )
}
