import { InfoRounded } from '@mui/icons-material'
import { Tooltip, Typography } from '@mui/material'

const TooltipMidi = () => (
  <Tooltip
    sx={{ cursor: 'help' }}
    placement="bottom-end"
    title={
      <div>
        <Typography color="HighlightText" variant="subtitle1">
          MIDI Device/s detected
        </Typography>
        <Typography color="textSecondary" variant="subtitle1">
          <em>Press a MIDI button to assign to this scene.</em>
        </Typography>
      </div>
    }
  >
    <InfoRounded />
  </Tooltip>
)

export default TooltipMidi
