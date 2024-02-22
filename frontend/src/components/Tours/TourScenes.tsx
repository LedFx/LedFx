import { useState } from 'react'
import { MenuItem, ListItemIcon, Badge } from '@mui/material'
import Tour from 'reactour'
import { InfoRounded } from '@mui/icons-material'
import useStore from '../../store/useStore'

const steps = [
  {
    selector: '.step-scenes-one',
    content: (
      <div>
        <h2>Scenes</h2>
        You can save the current state of LedFx as a scene, while giving it a
        name and optionally an image or an icon.
        <p>
          Note: This includes all active effects for all devices and their
          effect-settings.
        </p>
      </div>
    ),
    style: {
      backgroundColor: '#303030'
    }
  }
]

const TourScenes = ({ cally }: any) => {
  const [isTourOpen, setIsTourOpen] = useState(false)
  const setTour = useStore((state) => state.setTour)
  const invisible = useStore((state) => state.tours.devices)

  return (
    <>
      <MenuItem
        onClick={(e) => {
          setIsTourOpen(true)
          cally(e)
          setTour('scenes')
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

export default TourScenes
