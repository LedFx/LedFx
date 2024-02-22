import { Stack, Box } from '@mui/material'

import useStyle from './SpWidgetPro.styles'
import SpControls from './SpControls'
import SpTrack from './SpTrack'
import SpVolume from './SpVolume'
import SpSceneTrigger from './SpSceneTrigger'
import useStore from '../../../../../store/useStore'
import SpLayoutButtons from './SpLayoutButtons'
import SpFloating from './SpFloating'

const SpotifyWidgetPro = ({ drag }: { drag?: boolean }) => {
  const classes = useStyle()
  const swSize = useStore((state) => state.spotify.swSize)

  return (
    <Box component={drag ? SpFloating : Box}>
      <div className={classes.Widget}>
        <Box className={`${classes.spWrapper} ${drag ? swSize : ''}`}>
          <SpTrack className={`${classes.spTrack} ${drag ? swSize : ''}`} />
          <SpControls className={drag ? swSize : ''} />
          <Stack className={`${classes.spDeskVol} ${drag ? swSize : ''}`}>
            <Stack direction="row">
              {drag && <SpLayoutButtons />}
              <SpSceneTrigger />
            </Stack>
            <SpVolume />
          </Stack>
        </Box>
      </div>
    </Box>
  )
}

SpotifyWidgetPro.defaultProps = {
  drag: false
}
export default SpotifyWidgetPro
