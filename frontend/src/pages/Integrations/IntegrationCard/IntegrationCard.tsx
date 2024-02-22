import { useState } from 'react'
import Card from '@mui/material/Card'
import Button from '@mui/material/Button'
import EditIcon from '@mui/icons-material/Edit'
import Collapse from '@mui/material/Collapse'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import IconButton from '@mui/material/IconButton'
import {
  Avatar,
  CardActions,
  CardHeader,
  Switch,
  useTheme
} from '@mui/material'
import Popover from '../../../components/Popover/Popover'
import useStore from '../../../store/useStore'
import useIntegrationCardStyles from './IntegrationCard.styles'
import BladeIcon from '../../../components/Icons/BladeIcon/BladeIcon'
// import SpotifyView from '../Spotify/SpotifyAuth';

const IntegrationCard = ({ integration }: any) => {
  const classes = useIntegrationCardStyles()
  const theme = useTheme()
  const getIntegrations = useStore((state) => state.getIntegrations)
  const integrations = useStore((state) => state.integrations)
  const deleteIntegration = useStore((state) => state.deleteIntegration)
  const toggleIntegration = useStore((state) => state.toggleIntegration)
  const setDialogOpenAddIntegration = useStore(
    (state) => state.setDialogOpenAddIntegration
  )

  const [expanded, setExpanded] = useState(false)
  const variant = 'outlined'
  const color = 'inherit'

  const handleExpandClick = () => {
    setExpanded(!expanded)
  }

  const handleDeleteDevice = (integ: string) => {
    deleteIntegration(integrations[integ].id).then(() => {
      getIntegrations()
    })
  }

  const handleEditIntegration = (integ: any) => {
    setDialogOpenAddIntegration(true, integ)
  }
  const handleActivateIntegration = (integ: any) => {
    toggleIntegration({
      id: integ.id
    }).then(() => getIntegrations())
  }

  return integrations[integration]?.config ? (
    <Card className={classes.integrationCardPortrait}>
      <CardHeader
        title={integrations[integration].config.name}
        subheader={integrations[integration].config.description}
        action={
          <Switch
            aria-label="status"
            checked={integrations[integration].active}
            onClick={() => handleActivateIntegration(integrations[integration])}
          />
        }
        avatar={
          <Avatar
            aria-label="recipe"
            sx={{ width: 56, height: 56, color: '#fff' }}
          >
            <BladeIcon
              name={
                integrations[integration].config.name.startsWith('Home')
                  ? 'homeAssistant'
                  : 'mdi:spotify'
              }
              style={{ fontSize: 48 }}
            />
          </Avatar>
        }
      />
      <CardActions style={{ alignSelf: 'flex-end' }}>
        <div className={classes.integrationCardContainer}>
          <IconButton
            sx={{
              display: 'none',
              transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
              marginLeft: 'auto',
              transition: theme.transitions.create('transform', {
                duration: theme.transitions.duration.shortest
              }),
              '@media (max-width: 580px)': {
                display: 'block'
              }
            }}
            onClick={handleExpandClick}
            aria-expanded={expanded}
            aria-label="show more"
          >
            <ExpandMoreIcon />
          </IconButton>
          <div className={classes.buttonBar}>
            <Popover
              variant={variant}
              color={color}
              onConfirm={() => handleDeleteDevice(integration)}
              className={classes.editButton}
            />

            <Button
              variant={variant}
              size="small"
              color={color}
              className={classes.editButton}
              onClick={() => handleEditIntegration(integration)}
            >
              <EditIcon />
            </Button>
          </div>
        </div>

        <Collapse
          in={expanded}
          timeout="auto"
          unmountOnExit
          className={classes.buttonBarMobile}
        >
          <div className={classes.buttonBarMobileWrapper}>
            <Popover
              variant={variant}
              color={color}
              onConfirm={() => handleDeleteDevice(integration)}
              className={classes.editButton}
            />
            <Button
              variant={variant}
              size="small"
              color={color}
              className={classes.editButtonMobile}
              onClick={() => handleEditIntegration(integration)}
            >
              <EditIcon />
            </Button>
          </div>
        </Collapse>
      </CardActions>
    </Card>
  ) : null
}

export default IntegrationCard
