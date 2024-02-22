/* eslint-disable no-plusplus */
import { useEffect } from 'react'
import { makeStyles } from '@mui/styles'
import { Alert, Collapse } from '@mui/material'
import useStore from '../../store/useStore'
import DeviceCard from './DeviceCard/DeviceCard.wrapper'
import NoYet from '../../components/NoYet'
import ws from '../../utils/Websocket'

const useStyles = makeStyles(() => ({
  cardWrapper: {
    // padding: theme.spacing(1),
    paddingTop: 0,
    display: 'flex',
    flexWrap: 'wrap',
    marginTop: '0.5rem',
    justifyContent: 'center'
  },
  '@media (max-width: 580px)': {
    cardWrapper: {
      justifyContent: 'center'
    }
  },
  '@media (max-width: 410px)': {
    cardWrapper: {
      padding: 0
    }
  }
}))

const Devices = () => {
  const classes = useStyles()
  const getDevices = useStore((state) => state.getDevices)
  const getVirtuals = useStore((state) => state.getVirtuals)
  const virtuals = useStore((state) => state.virtuals)
  const setPixelGraphs = useStore((state) => state.setPixelGraphs)
  const graphs = useStore((state) => state.graphsMulti)
  const graphsMulti = useStore((state) => state.graphsMulti)
  const infoAlerts = useStore((state) => state.ui.infoAlerts)
  const setInfoAlerts = useStore((state) => state.ui.setInfoAlerts)
  const fPixels = useStore((state) => state.config.visualisation_maxlen)

  useEffect(() => {
    getDevices()
    getVirtuals()
  }, [getDevices, getVirtuals])

  useEffect(() => {
    const handleWebsockets = (e: any) => {
      if (e.detail === 'devices_updated') {
        getDevices()
      }
    }
    document.addEventListener('devices_updated', handleWebsockets)
    return () => {
      document.removeEventListener('devices_updated', handleWebsockets)
    }
  }, [getDevices])

  useEffect(() => {
    const handleWebsockets = () => {
      const req = {
        event_type: 'devices_updated',
        id: 1,
        type: 'subscribe_event'
      }
      // console.log("Send");
      ;(ws as any).send(JSON.stringify(++req.id && req))
    }
    document.addEventListener('devices_updated', handleWebsockets)
    return () => {
      document.removeEventListener('devices_updated', handleWebsockets)
    }
  }, [fPixels])

  useEffect(() => {
    if (graphs && graphsMulti) {
      setPixelGraphs(Object.keys(virtuals))
    }
  }, [graphs, graphsMulti, setPixelGraphs])

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        flexDirection: 'column'
      }}
    >
      <Collapse in={infoAlerts.devices}>
        <Alert
          severity="info"
          onClose={() => {
            setInfoAlerts('devices', false)
          }}
        >
          Use the + Button to add a new device or virtual.
          <br />
          Virtuals can be used to <strong>split</strong> or{' '}
          <strong> group</strong> segments of devices.
        </Alert>
      </Collapse>
      <div className={classes.cardWrapper}>
        {virtuals && Object.keys(virtuals).length ? (
          Object.keys(virtuals).map((virtual, i) => (
            <DeviceCard virtual={virtual} key={i} index={i} />
          ))
        ) : (
          <NoYet type="Device" />
        )}
      </div>
    </div>
  )
}

export default Devices
