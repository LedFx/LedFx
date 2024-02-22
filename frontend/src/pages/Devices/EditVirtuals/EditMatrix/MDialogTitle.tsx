import { DialogTitle, Typography } from '@mui/material'
import useStyles from './M.styles'

const MDialogTitle = ({
  currentCell,
  m
}: {
  currentCell: number[]
  m: any[]
}) => {
  const classes = useStyles()

  return (
    <DialogTitle>
      <div className={classes.centered}>
        {currentCell[1] >= 0 &&
        currentCell[0] >= 0 &&
        m[currentCell[1]][currentCell[0]]?.deviceId !== ''
          ? 'Edit'
          : 'Assign'}{' '}
        Pixel
        <Typography variant="caption" align="right">
          Row: {currentCell[1] + 1}
          <br />
          Column: {currentCell[0] + 1}
        </Typography>
      </div>
    </DialogTitle>
  )
}

export default MDialogTitle
