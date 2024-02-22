import { useState } from 'react'
import { MenuItem, ListItemIcon, Badge } from '@mui/material'
import Tour from 'reactour'
import { InfoRounded } from '@mui/icons-material'
import useStore from '../../store/useStore'

const steps = [
  {
    selector: '.step-integrations-one',
    content: (
      <div>
        <h2>Integrations</h2>
        Text for Integrations
      </div>
    ),
    style: {
      backgroundColor: '#303030'
    }
  }
]

const TourIntegrations = ({ cally }: any) => {
  const [isTourOpen, setIsTourOpen] = useState(false)
  const setTour = useStore((state) => state.setTour)
  const invisible = useStore((state) => state.tours.integrations)

  return (
    <>
      <MenuItem
        onClick={(e) => {
          setIsTourOpen(true)
          cally(e)
          setTour('integrations')
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

export default TourIntegrations
