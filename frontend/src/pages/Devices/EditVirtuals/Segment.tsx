import { useEffect } from 'react'
import { Typography, Button, Stack } from '@mui/material'
import { ExpandLess, ExpandMore, SwapHoriz } from '@mui/icons-material'
import { swap } from '../../../utils/helpers'
import PopoverSure from '../../../components/Popover/Popover'
import PixelSlider from './PixelSlider'
import useStore from '../../../store/useStore'
import useSegmentStyles from './Segment.styles'

const Segment = ({ s, i, virtual, segments, calib }: any) => {
  const getDevices = useStore((state) => state.getDevices)
  const devices = useStore((state) => state.devices)

  const title =
    devices &&
    devices[devices && Object.keys(devices).find((d) => d === s[0])!].config!
      .name
  const classes = useSegmentStyles()
  const updateSegments = useStore((state) => state.updateSegments)
  const highlightSegment = useStore((state) => state.highlightSegment)
  const highlightOffSegment = useStore((state) => state.highlightOffSegment)
  const getVirtuals = useStore((state) => state.getVirtuals)
  const activeSegment = useStore((state) => state.activeSegment)
  const setActiveSegment = useStore((state) => state.setActiveSegment)

  const handleInvert = () => {
    const newSegments = segments.map((seg: any[], index: number) =>
      index === i ? [seg[0], seg[1], seg[2], !seg[3]] : seg
    )
    updateSegments(virtual.id, newSegments).then(() => {
      getVirtuals()
      if (calib) {
        highlightSegment(
          virtual.id,
          newSegments[i][0],
          newSegments[i][1],
          newSegments[i][2],
          newSegments[i][3]
        )
        setActiveSegment(i)
      }
    })
  }
  const reorder = (direction: string) => {
    const newSegments =
      direction === 'UP' ? swap(segments, i - 1, i) : swap(segments, i, i + 1)
    updateSegments(virtual.id, newSegments).then(() => {
      getVirtuals()
      if (calib) {
        highlightSegment(
          virtual.id,
          newSegments[direction === 'UP' ? i - 1 : i + 1][0],
          newSegments[direction === 'UP' ? i - 1 : i + 1][1],
          newSegments[direction === 'UP' ? i - 1 : i + 1][2],
          newSegments[direction === 'UP' ? i - 1 : i + 1][3]
        )
        setActiveSegment(direction === 'UP' ? i - 1 : i + 1)
      }
    })
  }
  const handleDeleteSegment = () => {
    const newSegments = segments.filter(
      (_seg: any, index: number) => index !== i
    )
    updateSegments(virtual.id, newSegments).then(() => {
      getVirtuals()
      if (calib) {
        highlightOffSegment(virtual.id)
        setActiveSegment(-1)
      }
    })
  }
  const handleRangeSegment = (start: number, end: number) => {
    const newSegments = segments.map((seg: any, index: number) =>
      index === i ? [seg[0], start, end, seg[3]] : seg
    )

    updateSegments(virtual.id, newSegments).then(() => {
      getVirtuals()
      if (calib) {
        highlightSegment(
          virtual.id,
          newSegments[i][0],
          newSegments[i][1],
          newSegments[i][2],
          newSegments[i][3]
        )
        setActiveSegment(i)
      }
    })
  }

  useEffect(() => {
    getDevices()
  }, [getDevices])

  return (
    <div
      style={{
        padding: '0 1rem',
        background: calib && i === activeSegment ? '#ffffff18' : ''
      }}
    >
      <div className={classes.segmentsWrapper}>
        <Stack direction="column" spacing={1} alignItems="flex-start">
          <Typography color="textSecondary" marginTop={1} marginBottom={-1}>
            {title}
          </Typography>
          <div className={classes.segmentsColOrder}>
            <div style={{ display: 'flex' }}>
              <div>
                <Button
                  disabled={i === 0}
                  color="inherit"
                  onClick={() => reorder('UP')}
                  size="small"
                  className={classes.segmentsButtonUp}
                >
                  <ExpandLess />
                </Button>
              </div>
              <div>
                <Button
                  disabled={i === virtual.segments.length - 1}
                  color="inherit"
                  onClick={() => reorder('DOWN')}
                  size="small"
                  className={classes.segmentsButtonDown}
                >
                  <ExpandMore />
                </Button>
              </div>
            </div>
          </div>
        </Stack>
        <div
          className={classes.segmentsColPixelSlider}
          style={{
            alignSelf: 'stretch',
            display: 'flex',
            flexDirection: 'column'
          }}
        >
          <PixelSlider s={s} handleRangeSegment={handleRangeSegment} />
        </div>
        <div className={classes.segmentsColActions}>
          <div>
            <Button
              variant={s[3] ? 'contained' : 'outlined'}
              color={s[3] ? 'primary' : 'inherit'}
              endIcon={<SwapHoriz />}
              onClick={handleInvert}
              style={{ margin: '0 1rem 0 1.5rem' }}
            >
              Flip
            </Button>
          </div>
          <PopoverSure
            variant="outlined"
            color="primary"
            onConfirm={handleDeleteSegment}
            style={{ padding: '5px' }}
          />
        </div>
      </div>
    </div>
  )
}

export default Segment
