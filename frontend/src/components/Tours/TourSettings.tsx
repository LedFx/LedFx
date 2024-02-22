/* eslint-disable jsx-a11y/alt-text */
import { useLayoutEffect, useState } from 'react'
import { MenuItem, ListItemIcon, Badge } from '@mui/material'
import Tour from 'reactour'
import { InfoRounded } from '@mui/icons-material'
import useStore from '../../store/useStore'
import gif from '../../assets/transitions.gif'

const steps = [
  {
    selector: '.step-settings',
    content: (
      <div>
        <h2>Settings Tour</h2>
        Explore details about each setting
      </div>
    ),
    style: {
      backgroundColor: '#303030'
    }
  },
  {
    selector: '.step-settings-four',
    content: (
      <div>
        <h2>Control Buttons</h2>
        No Explanation needed
      </div>
    ),
    style: {
      backgroundColor: '#303030'
    }
  },
  {
    selector: '.step-settings-six',
    content: (
      <div>
        <h2>Global Transitions</h2>
        Mirror Transition-Changes to all devices
      </div>
    ),
    style: {
      backgroundColor: '#303030'
    }
  },
  {
    selector: '.step-settings-seven',
    content: (
      <div>
        <h2>Scan on startup</h2>
        Scan for WLEDs on startup
      </div>
    ),
    style: {
      backgroundColor: '#303030'
    }
  },
  {
    selector: '.step-settings-one',
    content: (
      <div>
        <h2>Audio Device</h2>
        Select your audio input device here.
        <p>Note: Additional Informations incoming</p>
      </div>
    ),
    style: {
      backgroundColor: '#303030'
    }
  },
  {
    selector: '.step-settings-two',
    content: (
      <div>
        <h2>Frontend FPS</h2>
        FPS sent to the frontend to render the PixelGraphs
        <p>
          Note: Low-end devices might struggle with too much data. Keep it at
          maximum, if everything runs smooth.
        </p>
      </div>
    ),
    style: {
      backgroundColor: '#303030'
    }
  },
  {
    selector: '.step-settings-three',
    content: (
      <div>
        <h2>Frontend Max Pixel Length</h2>
        Pixels per device sent to the frontend to render the PixelGraphs
        <p>Note: Low-end devices might struggle with too much data.</p>
      </div>
    ),
    style: {
      backgroundColor: '#303030'
    }
  },
  {
    selector: '.step-settings-five',
    content: (
      <div>
        <h2>WLED Integration</h2>
        Finetune how LedFx should handle your WLEDs
      </div>
    ),
    style: {
      backgroundColor: '#303030'
    }
  },
  {
    selector: '.step-settings-eight',
    content: (
      <div>
        <h2>Transitions</h2>
        <p>Finetune how LedFx change from one effect to another</p>
        <div style={{ display: 'flex' }}>
          <img src={gif} />
        </div>
      </div>
    ),
    style: {
      backgroundColor: '#303030',
      maxWidth: 600
    }
  }
]

const TourSettings = ({ cally }: any) => {
  const [isTourOpen, setIsTourOpen] = useState(false)
  const setTour = useStore((state) => state.setTour)
  const invisible = useStore((state) => state.tours.settings)
  const settingsExpanded = useStore((state) => state.ui.settingsExpanded)
  const setSettingsExpanded = useStore((state) => state.ui.setSettingsExpanded)
  const features = useStore((state) => state.features)

  useLayoutEffect(() => {
    if (isTourOpen && settingsExpanded !== 'all') {
      setSettingsExpanded('all')
    }
  }, [isTourOpen])

  return (
    <>
      <MenuItem
        onClick={(e) => {
          setIsTourOpen(true)
          cally(e)
          setTour('settings')
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
        steps={
          features.wled
            ? steps
            : steps.filter((s) => s.selector !== '.step-settings-five')
        }
        accentColor="#800000"
        isOpen={isTourOpen}
        onRequestClose={() => {
          setSettingsExpanded('false')
          setIsTourOpen(false)
        }}
      />
    </>
  )
}

export default TourSettings
