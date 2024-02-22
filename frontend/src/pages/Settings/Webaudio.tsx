/* eslint-disable @typescript-eslint/indent */
/* eslint-disable no-console */
/* eslint-disable no-plusplus */
/* eslint-disable func-names */
import {
  Button,
  Fab,
  TextField,
  Popover,
  Select,
  MenuItem,
  Stack
} from '@mui/material'
import { Check, Close } from '@mui/icons-material'
import { useState, useEffect, CSSProperties } from 'react'
import BladeIcon from '../../components/Icons/BladeIcon/BladeIcon'
import ws from '../../utils/Websocket'
import useStore from '../../store/useStore'

const getMedia = async (clientDevice: MediaDeviceInfo) => {
  const audioSetting: boolean | MediaTrackConstraints | undefined =
    await navigator.mediaDevices
      .enumerateDevices()
      .then(function (devices): any {
        return clientDevice === null || devices.indexOf(clientDevice) === -1
          ? true
          : { deviceId: { exact: clientDevice } }
      })
  try {
    return await navigator.mediaDevices.getUserMedia({
      audio: audioSetting,
      video: false
    })
  } catch (err) {
    return console.log('Error:', err)
  }
}

const Webaudio = ({ style }: { style: CSSProperties }) => {
  const webAud = useStore((state) => state.webAud)
  const setWebAud = useStore((state) => state.setWebAud)
  const [wsReady, setWsReady] = useState(false)
  const webAudName = useStore((state) => state.webAudName)
  const setWebAudName = useStore((state) => state.setWebAudName)
  const webAudTypes = [
    {
      label: 'ws-v1',
      value: 'audio_stream_data'
    },
    {
      label: 'ws-v2',
      value: 'audio_stream_data_v2'
    },
    {
      label: 'udp',
      value: 'audio_stream_data_udp'
    }
  ]
  const [webAudType, setWebAudType] = useState(webAudTypes[1].value)
  const [webAudConfig, setWebAudConfig] = useState({
    sampleRate: 44100,
    bufferSize: 1024,
    udpPort: 8000
  })
  const [bit, setBit] = useState(16)

  useEffect(() => {
    if (webAudType === 'audio_stream_data_udp') {
      setBit(8)
    } else if (webAudType === 'audio_stream_data_v1') {
      setBit(32)
    } else {
      setBit(16)
    }
  }, [webAudType])

  const audioContext =
    webAud && new (window.AudioContext || (window as any).webkitAudioContext)()
  const [anchorEl, setAnchorEl] = useState(null)

  const getSchemas = useStore((state) => state.getSchemas)
  const clientDevice = useStore((state) => state.clientDevice)
  const setClientDevices = useStore((state) => state.setClientDevices)

  const handleClick = (event: any) => {
    setAnchorEl(event.currentTarget)
  }
  const handleClose = () => {
    setAnchorEl(null)
  }
  const open = Boolean(anchorEl)
  const id = open ? 'simple-popover' : undefined

  let s: MediaStream
  useEffect(() => {
    if (webAud) {
      getMedia(clientDevice).then((stream) => {
        if (stream) {
          s = stream
          if (!audioContext || audioContext.state === 'closed') {
            return
          }

          const source = stream && audioContext.createMediaStreamSource(stream)
          const scriptNode = audioContext.createScriptProcessor(1024, 1, 1)
          // const analyser = audioContext.createAnalyser()
          // // const scriptNode = audioContext.createScriptProcessor(0, 1, 1);
          // console.log("THIS", analyser);
          source.connect(scriptNode)
          // analyser.connect(scriptNode);
          scriptNode.connect(audioContext.destination)
          if (wsReady) {
            if (webAud) {
              const sendWs = async () => {
                const i = 0
                const request = {
                  data: {
                    sampleRate: scriptNode?.context?.sampleRate,
                    bufferSize: scriptNode?.bufferSize,
                    ...(webAudType === 'audio_stream_data_udp'
                      ? {
                          udpPort: webAudConfig.udpPort,
                          bit
                        }
                      : {})
                  },
                  client: webAudName,
                  id: i,
                  type: 'audio_stream_config'
                }
                ;(ws as any).ws.send(JSON.stringify(++request.id && request))
              }
              sendWs()
            }
          }
          scriptNode.onaudioprocess = (e) => {
            if (wsReady) {
              if (webAud) {
                const sendWsV2 = async () => {
                  const i = 0
                  const floatData = e.inputBuffer.getChannelData(0)
                  const int16Array = new Int16Array(floatData.length)
                  for (let j = 0; j < floatData.length; j++) {
                    int16Array[j] = floatData[j] * 32767
                  }
                  const uint8Array = new Uint8Array(int16Array.buffer)
                  const numberArray = Array.from(uint8Array)
                  const binaryString = String.fromCharCode.apply(
                    null,
                    numberArray
                  )
                  const base64String = btoa(binaryString)
                  const request = {
                    data: base64String,
                    client: webAudName,
                    id: i,
                    type: 'audio_stream_data_v2'
                  }
                  ;(ws as any).ws.send(JSON.stringify(++request.id && request))
                }
                const sendWsV1 = async () => {
                  const i = 0
                  const request = {
                    data: e.inputBuffer.getChannelData(0),
                    client: webAudName,
                    id: i,
                    type: 'audio_stream_data'
                  }
                  ;(ws as any).ws.send(JSON.stringify(++request.id && request))
                }
                if (webAudType === 'audio_stream_data_v2') {
                  sendWsV2()
                } else {
                  sendWsV1()
                }
              }
            }
          }
        }
      })
    }
  }, [audioContext])

  if (!wsReady) {
    if (ws && (ws as any).ws && (ws as any).ws.readyState === 1) {
      setWsReady(true)
    }
  }

  return (
    <>
      <Fab
        aria-describedby={id}
        size="large"
        color={webAud ? 'inherit' : 'secondary'}
        onClick={(e: any) => {
          if (webAud) {
            if (audioContext) {
              s.getTracks().forEach((track) => track.stop())
              audioContext.close()
            }
            const sendWs = async () => {
              const i = 0
              const request = {
                client: webAudName,
                id: i,
                type: 'audio_stream_stop'
              }
              ;(ws as any).ws.send(JSON.stringify(++request.id && request))
            }
            sendWs().then(() => getSchemas())
            setWebAud(false)
            setClientDevices(null)
            window.location.reload()
          } else {
            handleClick(e)
          }
        }}
        data-webaud={webAud}
        style={style}
      >
        {!webAud ? (
          <>
            <BladeIcon
              name="mdi:wifi"
              colorIndicator={webAud}
              style={{
                position: 'relative',
                transform: 'scale(0.8) translate(20%,-30%)'
              }}
            />
            <BladeIcon
              name="mdi:microphone"
              colorIndicator={webAud}
              style={{
                position: 'absolute',
                transform: 'scale(0.7) translate(-20%,50%)'
              }}
            />
          </>
        ) : (
          <BladeIcon
            name="mdi:stop"
            colorIndicator={webAud}
            style={{ position: 'relative' }}
          />
        )}
      </Fab>
      <Popover
        id={id}
        open={open}
        anchorEl={anchorEl}
        onClose={handleClose}
        anchorOrigin={{
          vertical: 'center',
          horizontal: 'left'
        }}
        transformOrigin={{
          vertical: 'center',
          horizontal: 'right'
        }}
      >
        <Stack spacing={2} sx={{ p: 2 }}>
          <TextField
            id="client-name"
            label="Client Name"
            value={webAudName}
            onChange={(e) => setWebAudName(e.target.value)}
            variant="outlined"
          />
          <Select
            value={webAudType}
            variant="outlined"
            onChange={(e) => setWebAudType(e.target.value)}
          >
            {webAudTypes.map((type) => (
              <MenuItem key={type.value} value={type.value}>
                {type.label}
              </MenuItem>
            ))}
          </Select>
          <TextField
            disabled
            id="sample-rate"
            label="Sample Rate"
            value={webAudConfig.sampleRate}
            type="number"
            onChange={(e) =>
              setWebAudConfig({
                ...webAudConfig,
                sampleRate: parseInt(e.target.value, 10)
              })
            }
            variant="outlined"
          />
          <TextField
            disabled
            id="buffer-size"
            label="Buffer Size"
            value={webAudConfig.bufferSize}
            onChange={(e) =>
              setWebAudConfig({
                ...webAudConfig,
                bufferSize: parseInt(e.target.value, 10)
              })
            }
            variant="outlined"
          />
          {webAudType === 'audio_stream_data_udp' && (
            <TextField
              id="udp-port"
              label="UDP Port"
              value={webAudConfig.udpPort}
              onChange={(e) =>
                setWebAudConfig({
                  ...webAudConfig,
                  udpPort: parseInt(e.target.value, 10)
                })
              }
              variant="outlined"
            />
          )}

          <TextField
            id="bit"
            disabled
            label="Bit"
            value={bit}
            onChange={(e) => setBit(parseInt(e.target.value, 10))}
            variant="outlined"
          />
          <Stack direction="row" spacing={2} justifyContent="space-between">
            <Button
              aria-describedby={id}
              variant="contained"
              color="primary"
              onClick={() => {
                setAnchorEl(null)
              }}
            >
              <Close />
            </Button>
            <Button
              aria-describedby={id}
              variant="contained"
              color="primary"
              onClick={() => {
                if (!webAud) {
                  if (wsReady) {
                    navigator.mediaDevices
                      .enumerateDevices()
                      .then(function (devices) {
                        setClientDevices(devices)
                      })
                      .catch(function (err) {
                        console.log(`${err.name}: ${err.message}`)
                      })
                    const sendWs = async () => {
                      const request = {
                        data: {},
                        client: webAudName,
                        id: 1,
                        type: 'audio_stream_start'
                      }
                      ;(ws as any).ws.send(
                        JSON.stringify(++request.id && request)
                      )
                    }
                    sendWs()
                    setTimeout(() => {
                      getSchemas()
                    }, 1000)
                  }
                }

                setAnchorEl(null)
                setWebAud(true)
              }}
            >
              <Check />
            </Button>
          </Stack>
        </Stack>
      </Popover>
      {/* <canvas width={dw} height={dh} style={style} ref={canvas} /> */}
    </>
  )
}

export default Webaudio
