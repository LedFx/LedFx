/* eslint-disable no-promise-executor-return */
/* eslint-disable no-plusplus */
/* eslint-disable no-await-in-loop */
import { useEffect, useState } from 'react'

import { useSnackbar } from 'notistack'

import useStore from '../../store/useStore'

import Dashboard from './Dashboard'
import DashboardDetailed from './DashboardDetailed'
import ws from '../../utils/Websocket'
import IntroDialog from '../../components/Dialogs/IntroDialog'

const sleep = (ms: number) => {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export default function Home() {
  const scanForDevices = useStore((state) => state.scanForDevices)
  const getDevices = useStore((state) => state.getDevices)
  const getVirtuals = useStore((state) => state.getVirtuals)
  // eslint-disable-next-line @typescript-eslint/no-unused-vars, no-unused-vars
  const [scanning, setScanning] = useState(-1)
  const [lastFound, setLastFound] = useState([] as string[])
  const features = useStore((state) => state.features)
  const intro = useStore((state) => state.intro)

  const { enqueueSnackbar } = useSnackbar()

  const handleScan = () => {
    setScanning(0)
    scanForDevices()
      .then(async () => {
        for (let sec = 1; sec <= 30; sec++) {
          await sleep(1000).then(() => {
            getDevices()
            getVirtuals()
            setScanning(Math.round((100 / 30) * sec))
          })
        }
      })
      .then(() => {
        setScanning(-1)
      })
  }

  useEffect(() => {
    const handleWebsockets = (e: any) => {
      if (e.detail.id === 'device_created') {
        if (lastFound.indexOf(e.detail.device_name) === -1) {
          enqueueSnackbar(`New Device added: ${e.detail.device_name}`, {
            variant: 'info'
          })
          setLastFound([...lastFound, e.detail.device_name])
          getDevices()
        }
      }
    }

    document.addEventListener('device_created', handleWebsockets)

    return () => {
      document.removeEventListener('device_created', handleWebsockets)
    }
  }, [])

  useEffect(() => {
    const handleWebsockets = () => {
      const req = {
        event_type: 'graph_update',
        id: 1337,
        type: 'subscribe_event'
      }
      // console.log("Send");
      ;(ws as any).send(JSON.stringify(++req.id && req))
    }
    document.addEventListener('subs_device_created', handleWebsockets)
    return () => {
      const removeGetWs = async () => {
        const request = {
          id: 1337,
          type: 'unsubscribe_event',
          event_type: 'graph_update'
        }
        ;(ws as any).send(JSON.stringify(++request.id && request))
      }
      // console.log("Clean Up");
      removeGetWs()
      document.removeEventListener('subs_device_created', handleWebsockets)
    }
  }, [])

  useEffect(() => {
    const handleWebsockets = () => {
      const req = {
        event_type: 'device_created',
        id: 1337,
        type: 'subscribe_event'
      }
      // console.log("Send");
      ;(ws as any).send(JSON.stringify(++req.id && req))
    }
    document.addEventListener('subs_device_created', handleWebsockets)
    return () => {
      const removeGetWs = async () => {
        const request = {
          id: 1337,
          type: 'unsubscribe_event',
          event_type: 'device_created'
        }
        ;(ws as any).send(JSON.stringify(++request.id && request))
      }
      // console.log("Clean Up");
      removeGetWs()
      document.removeEventListener('subs_device_created', handleWebsockets)
    }
  }, [])

  return !intro ? (
    features.dashboardDetailed ? (
      <DashboardDetailed />
    ) : (
      <Dashboard />
    )
  ) : (
    <IntroDialog
      scanning={scanning}
      handleScan={handleScan}
      setScanning={setScanning}
    />
  )
}
