import { useState } from 'react'
import { MenuItem, ListItemIcon, Badge } from '@mui/material'
import Tour from 'reactour'
import { InfoRounded } from '@mui/icons-material'
import useStore from '../../store/useStore'

const steps = [
  {
    selector: '.step-device-one',
    content: (
      <div>
        <h2>Effect Type</h2>
        Choose an effect here.
        <ul style={{ paddingLeft: '1rem' }}>
          <li>BASIC: Simple, non reactive effects</li>
          <li>1.0: Audio reactive effects</li>
          <li>2D: [WIP] Effects designed for a 2D LED matrix</li>
          <li>BPM: Effects designed for the beat of your music</li>
          <li>2.0: Experimental new audio reactive effects</li>
        </ul>
        <li>Each effect has plenty of settings to play with</li>
        <li>You can tune effects to your liking</li>
      </div>
    ),
    style: {
      backgroundColor: '#303030'
    }
  },
  {
    selector: '.step-device-two',
    content: (
      <div>
        <h2>Transitions</h2>
        <li>You can adjust the animation between effects</li>
        <li>Set to 0 for no animation</li>
      </div>
    ),
    style: {
      backgroundColor: '#303030'
    }
  },
  {
    selector: '.step-device-three',
    content: (
      <div>
        <h2>Presets</h2>
        Easily save and apply the settings of an effect. LedFx has some built in
        presets, and you can save your own too
      </div>
    ),
    style: {
      backgroundColor: '#303030'
    }
  },
  {
    selector: '.step-device-four',
    content: (
      <div>
        <h2>Frequency Range</h2>
        <li>Adjust the audio frequency range used for effects</li>
        <li>Most 1.0 effects will work with any frequency range you specify</li>
        <li>
          Some effects will bypass this and do their own internal analysis
        </li>
      </div>
    ),
    style: {
      backgroundColor: '#303030'
    }
  },
  {
    selector: '.step-device-five',
    content: (
      <div>
        <h2>Clear Effect</h2>
        Clear effect and release device
      </div>
    ),
    style: {
      backgroundColor: '#303030'
    }
  },
  {
    selector: '.step-device-six',
    content: (
      <div>
        <h2>Pause streaming</h2>
        Pause streaming to leds
      </div>
    ),
    style: {
      backgroundColor: '#303030'
    }
  },
  {
    selector: '.step-device-seven',
    content: (
      <div>
        <h2>Effect Tours</h2>
        Every effect has an individual tour to explain the different properties
      </div>
    ),
    style: {
      backgroundColor: '#303030'
    }
  }
]

const TourDevice = ({ cally }: any) => {
  const [isTourOpen, setIsTourOpen] = useState(false)
  const setTour = useStore((state) => state.setTour)
  const invisible = useStore((state) => state.tours.device)

  return (
    <>
      <MenuItem
        onClick={(e) => {
          setIsTourOpen(true)
          cally(e)
          setTour('device')
        }}
      >
        <ListItemIcon>
          <Badge variant="dot" color="error" invisible={invisible}>
            <InfoRounded />
          </Badge>
        </ListItemIcon>
        Tour
      </MenuItem>
      <Tour
        steps={steps}
        accentColor="#800000"
        isOpen={isTourOpen}
        onRequestClose={() => setIsTourOpen(false)}
      />
    </>
  )
}

export default TourDevice
