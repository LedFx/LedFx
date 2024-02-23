import { useEffect } from 'react'
import { makeStyles } from '@mui/styles'
import useStore from '../../store/useStore'
import IntegrationCard from './IntegrationCard/IntegrationCard'
import NoYet from '../../components/NoYet'
import IntegrationCardSpotify from './IntegrationCard/IntegrationCardSpotify'
import IntegrationCardQLC from './IntegrationCard/IntegrationCardQLC'

const useStyles = makeStyles(() => ({
  cardWrapper: {
    display: 'flex',
    flexWrap: 'wrap',
    marginTop: '0.5rem',
    justifyContent: 'center'
  },
  '@media (max-width: 580px)': {
    cardWrapper: {
      justifyContent: 'center'
    }
  }
}))

const Integrations = () => {
  const classes = useStyles()
  const getIntegrations = useStore((state) => state.getIntegrations)
  const integrations = useStore((state) => state.integrations)

  useEffect(() => {
    getIntegrations()
  }, [getIntegrations])
  return (
    <div className={classes.cardWrapper}>
      {integrations && Object.keys(integrations).length ? (
        Object.keys(integrations).map((integration, i) =>
          integrations[integration].type === 'spotify' ? (
            <IntegrationCardSpotify integration={integration} key={i} />
          ) : integrations[integration].type === 'qlc' ? (
            <IntegrationCardQLC integration={integration} key={i} />
          ) : (
            <IntegrationCard integration={integration} key={i} />
          )
        )
      ) : (
        <NoYet type="Integration" />
      )}
    </div>
  )
}

export default Integrations
