/* eslint-disable react/require-default-props */
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import CardHeader from '@mui/material/CardHeader'
import FormControl from '@mui/material/FormControl'
import MenuItem from '@mui/material/MenuItem'
import InputLabel from '@mui/material/InputLabel'
import { Button, Chip, OutlinedInput, Select, Box } from '@mui/material'
import { useEffect, useRef, useState } from 'react'
import useStore from '../../store/useStore'
import { deepEqual } from '../../utils/helpers'

const ITEM_HEIGHT = 48
const ITEM_PADDING_TOP = 8
const MenuProps = {
  PaperProps: {
    style: {
      maxHeight: ITEM_HEIGHT * 4.5 + ITEM_PADDING_TOP,
      width: 250
    }
  }
}

const StreamToCard = ({
  virtual,
  virtuals,
  style
}: {
  virtual: {
    id: string
  }
  virtuals: any
  style?: any
}) => {
  const cref = useRef<any>(null)
  const streamingToDevices = useStore((state) => state.streamingToDevices)
  const setStreamingToDevices = useStore((state) => state.setStreamingToDevices)
  const streaming = useStore((state) => state.streaming)
  const setStreaming = useStore((state) => state.setStreaming)
  const getVirtuals = useStore((state) => state.getVirtuals)

  const [streamingTo, setStreamingTo] = useState(streamingToDevices)
  const copyTo = useStore((state) => state.copyTo)

  const handleToggle = (value: string) => {
    const currentIndex = streamingTo.indexOf(value)
    const newStreamingDevices = [...streamingTo]
    if (currentIndex === -1) {
      newStreamingDevices.push(value)
    } else {
      newStreamingDevices.splice(currentIndex, 1)
    }
    setStreamingTo(newStreamingDevices)
    setStreamingToDevices(newStreamingDevices)
  }

  const handleCopy = () =>
    copyTo(virtual.id, streamingTo).then(() => getVirtuals())

  useEffect(() => {
    if (streaming) {
      if (!deepEqual(cref.current, virtuals[virtual.id]?.effect)) {
        if (cref.current !== null) handleCopy()
        cref.current = virtuals[virtual.id]?.effect
      }
    }
  }, [virtuals[virtual.id]?.effect])

  return (
    <Card variant="outlined" className="step-device-twob" style={style}>
      <CardHeader
        title="Copy To"
        subheader="Copy current effect configurations other Devices"
        style={{ paddingBottom: 11 }}
      />
      <CardContent
        sx={{
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'center',
          width: '100%',
          p: '0.25rem 1rem 0.4rem 0.4rem !important'
        }}
      >
        <FormControl style={{ margin: 10, width: '100%' }}>
          <InputLabel id="streamto-label">
            Select device(s) to copy to
          </InputLabel>
          <Select
            labelId="streamto-label"
            id="streamto"
            multiple
            value={streamingTo}
            onChange={(e, b: any) => handleToggle(b.props.value)}
            input={
              <OutlinedInput
                id="select-multiple-chip"
                label="Select device(s) to copy to"
              />
            }
            renderValue={(selected: any) => (
              <Box sx={{ display: 'flex', flexWrap: 'wrap' }}>
                {selected.map((value: string) => (
                  <Chip key={value} label={value} />
                ))}
              </Box>
            )}
            MenuProps={MenuProps}
          >
            {Object.keys(virtuals).map((name) => (
              <MenuItem key={name} value={name}>
                {name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <Button size="medium" onClick={() => handleCopy()}>
            Copy
          </Button>
          <Button
            size="medium"
            onClick={() => setStreaming(!streaming)}
            color={streaming ? 'primary' : 'inherit'}
          >
            Sync
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

export default StreamToCard
