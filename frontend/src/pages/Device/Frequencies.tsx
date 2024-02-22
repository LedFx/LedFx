/* eslint-disable react/jsx-no-duplicate-props */
import { useState } from 'react'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import CardHeader from '@mui/material/CardHeader'
import Tooltip from '@mui/material/Tooltip'
import Slider from '@mui/material/Slider'
import { InputAdornment, TextField } from '@mui/material'
import useStore from '../../store/useStore'
import BladeFrame from '../../components/SchemaForm/components/BladeFrame'

const log13 = (x: number) => Math.log(x) / Math.log(13)
const logIt = (x: number) => 3700.0 * log13(1 + x / 200.0)
const hzIt = (x: number) => 200.0 * 13 ** (x / 3700.0) - 200.0

function ValueLabelComponent(props: any) {
  const { children, open, value } = props

  return (
    <Tooltip
      open={open}
      enterTouchDelay={0}
      placement="top"
      title={`${Math.round(hzIt(value))} Hz`}
    >
      {children}
    </Tooltip>
  )
}

const FrequenciesCard = ({ virtual, style }: any) => {
  const addVirtual = useStore((state) => state.addVirtual)
  const getVirtuals = useStore((state) => state.getVirtuals)
  const config = useStore((state) => state.config)

  const [value, setValue] = useState([
    logIt(virtual.config.frequency_min),
    logIt(virtual.config.frequency_max)
  ])

  const freq_max = config.melbanks?.max_frequencies.map((f: number) => ({
    value: f,
    label: `${f > 1000 ? `${f / 1000}kHz` : `${f}Hz`}`
  }))

  const freq_min = {
    value: config.melbanks?.min_frequency,
    label: `${
      config.melbanks?.min_frequency > 1000
        ? `${(config.melbanks?.min_frequency || 0) / 1000}kHz`
        : `${config.melbanks?.min_frequency}Hz`
    }`
  }
  const marks = freq_max && [freq_min, ...freq_max]

  const convertedMarks = marks?.map((m: any) => ({
    value: logIt(m.value),
    label: m.label
  }))

  const handleChange = (_event: React.ChangeEvent<any>, newValue: number[]) => {
    const copy = [...newValue]
    convertedMarks.forEach((m: any) => {
      if (Math.abs(newValue[0] - m.value) < 100) {
        copy[0] = m.value
      }
      if (Math.abs(newValue[1] - m.value) < 100) {
        copy[1] = m.value
      }
    })
    setValue(copy)
  }

  return (
    <Card variant="outlined" className="step-device-four" style={style}>
      <CardHeader
        title="Frequencies"
        subheader="Adjust the audio range used for this strip"
      />
      <CardContent
        sx={{
          display: 'flex',
          alignItems: 'center',
          width: '100%',
          padding: '0 1rem 0.75rem 0.9rem !important'
        }}
      >
        <div style={{ width: '100%' }}>
          <BladeFrame
            title="Range"
            style={{ padding: '16px 2rem 6px 2rem', marginBottom: '1rem' }}
          >
            <Slider
              value={[value[0], value[1]]}
              aria-labelledby="discrete-slider-custom"
              step={0.001}
              valueLabelDisplay="auto"
              marks={convertedMarks}
              min={logIt(config.melbanks?.min_frequency)}
              max={logIt(
                config.melbanks?.max_frequencies[
                  (config.melbanks?.max_frequencies.length || 1) - 1
                ]
              )}
              onChange={(e: any, v: any) => handleChange(e, v)}
              components={{ ValueLabel: ValueLabelComponent }}
              sx={{ color: '#aaa' }}
              onChangeCommitted={() => {
                // Backend cannot do partial updates yet, sending whole config
                addVirtual({
                  id: virtual.id,
                  config: {
                    ...virtual.config,
                    frequency_min: Math.round(hzIt(value[0])),
                    frequency_max: Math.round(hzIt(value[1]))
                  }
                }).then(() => getVirtuals())
              }}
            />
          </BladeFrame>
          <div
            style={{
              width: '100%',
              display: 'flex',
              justifyContent: 'space-between'
            }}
          >
            <div style={{ maxWidth: '120px' }}>
              <TextField
                id="min"
                label="Min"
                type="number"
                InputLabelProps={{
                  shrink: true
                }}
                InputProps={{
                  endAdornment: (
                    <InputAdornment position="end">Hz</InputAdornment>
                  )
                }}
                inputProps={{
                  style: { textAlign: 'right' },
                  min: 20,
                  max: 20000
                }}
                value={
                  Math.round(hzIt(value[0])) < 5
                    ? value[0]
                    : Math.round(hzIt(value[0]))
                }
                onChange={(e: any) => {
                  setValue([logIt(e.target.value), value[1]])
                }}
              />
            </div>
            <div style={{ maxWidth: '120px' }}>
              <TextField
                id="max"
                label="Max"
                type="number"
                value={
                  Math.round(hzIt(value[1])) > 20001
                    ? value[1]
                    : Math.round(hzIt(value[1]))
                }
                onChange={(e: any) => {
                  setValue([value[0], logIt(e.target.value)])
                }}
                inputProps={{
                  min: 20,
                  max: 20000
                }}
                InputLabelProps={{
                  shrink: true
                }}
                InputProps={{
                  endAdornment: (
                    <InputAdornment position="end">Hz</InputAdornment>
                  )
                }}
              />
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export default FrequenciesCard
