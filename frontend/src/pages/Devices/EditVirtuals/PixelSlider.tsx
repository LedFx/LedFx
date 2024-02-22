import { useEffect, useState } from 'react'
import { useThrottledCallback } from 'use-debounce'
import Slider from '@mui/material/Slider'
import { Stack, TextField } from '@mui/material'
import useStore from '../../../store/useStore'

const PixelSlider = ({ s, handleRangeSegment }: any) => {
  const getDevices = useStore((state) => state.getDevices)
  const devices = useStore((state) => state.devices)

  const [range, setRange] = useState([s[1], s[2]])

  useEffect(() => {
    getDevices()
  }, [getDevices])

  useEffect(() => {
    setRange([s[1], s[2]])
  }, [s])

  if (!devices[s[0]]) {
    return null
  }

  const pixelRange = [s[1], s[2]]

  const handleChange = (_event: any, newValue: any) => {
    if (newValue !== pixelRange) {
      handleRangeSegment(newValue[0], newValue[1])
    }
  }
  const throttled = useThrottledCallback(handleChange, 100)

  const marks = [
    { value: 0, label: 1 },
    {
      value: devices[s[0]].config.pixel_count - 1,
      label: devices[s[0]].config.pixel_count
    }
  ]

  return (
    <Stack direction="row" spacing={5} alignItems="flex-start" flexBasis="100%">
      <Stack
        direction="row"
        spacing={1}
        alignItems="flex-start"
        alignSelf="flex-end"
      >
        <TextField
          size="small"
          type="number"
          sx={{ minWidth: '80px' }}
          InputProps={{
            inputProps: {
              style: { padding: '4.5px 14px' },
              min: 1,
              max: devices[s[0]].config.pixel_count
            }
          }}
          value={range[0] + 1}
          onChange={(
            e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
          ) => {
            if (parseInt(e.target.value, 10) > range[1] + 1) {
              return
            }
            if (parseInt(e.target.value, 10) < 1) {
              setRange([0, range[1]])
              throttled(e, [0, range[1]])
              return
            }
            setRange([parseInt(e.target.value, 10) - 1, range[1]])
            throttled(e, [parseInt(e.target.value, 10) - 1, range[1]])
          }}
        />
        <TextField
          size="small"
          type="number"
          sx={{ minWidth: '80px' }}
          InputProps={{
            inputProps: {
              style: { padding: '4.5px 14px' },
              min: range[0] + 1,
              max: devices[s[0]].config.pixel_count
            }
          }}
          value={range[1] + 1}
          onChange={(
            e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
          ) => {
            if (e.target.value === '') {
              setRange([range[0], range[0] + 1])
              throttled(e, [range[0], range[0] + 1])
              return
            }
            if (parseInt(e.target.value, 10) < range[0] + 1) {
              setRange([range[0], range[0] + 1])
              throttled(e, [range[0], range[0] + 1])
              return
            }
            if (
              parseInt(e.target.value, 10) > devices[s[0]].config.pixel_count
            ) {
              setRange([range[0], devices[s[0]].config.pixel_count - 1])
              throttled(e, [range[0], devices[s[0]].config.pixel_count - 1])
              return
            }
            setRange([range[0], parseInt(e.target.value, 10) - 1])
            throttled(e, [range[0], parseInt(e.target.value, 10) - 1])
          }}
        />
      </Stack>
      <Slider
        sx={{ alignSelf: 'center' }}
        value={range}
        marks={marks}
        valueLabelFormat={(e) => e + 1}
        min={0}
        max={devices[s[0]].config.pixel_count - 1}
        onChange={(_event: any, n: any) => {
          setRange(n)
          throttled(_event, n)
        }}
        aria-labelledby="range-slider"
        valueLabelDisplay="auto"
      />
    </Stack>
  )
}

export default PixelSlider
