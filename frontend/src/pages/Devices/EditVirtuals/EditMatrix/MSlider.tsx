import { Slider } from '@mui/material'
import BladeFrame from '../../../../components/SchemaForm/components/BladeFrame'

const MSlider = ({
  group,
  devices,
  currentDevice,
  selectedPixel,
  handleSliderChange
}: {
  group: boolean
  devices: any
  selectedPixel: number | number[]
  currentDevice: any
  handleSliderChange: any
}) => {
  return (
    <BladeFrame
      title={`Pixel${group ? 's' : ''}`}
      full={false}
      style={{ marginBottom: '1rem' }}
    >
      <Slider
        marks={[
          { value: 0, label: '0' },
          {
            value: devices[currentDevice].config.pixel_count,
            label: devices[currentDevice].config.pixel_count
          }
        ]}
        valueLabelDisplay="auto"
        min={0}
        max={devices[currentDevice].config.pixel_count}
        value={selectedPixel}
        onChange={handleSliderChange}
      />
    </BladeFrame>
  )
}

export default MSlider
