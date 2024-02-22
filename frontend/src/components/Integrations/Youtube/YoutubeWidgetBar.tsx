import { Button, IconButton, Slider, Typography } from '@mui/material'
import { QueueMusic } from '@mui/icons-material'
import useAPIPolling, { APIPollingOptions } from 'use-api-polling'
import BladeIcon from '../../Icons/BladeIcon/BladeIcon'
import ChangeYoutubeURLDialog from './ChangeYoutubeURLDialog'

const YoutubeWidgetBar = ({
  youtubeEnabled,
  youtubeExpanded,
  setYoutubeExpanded,
  youtubeURL,
  setYoutubeURL,
  botHeight,
  state,
  setState
}: any) => {
  const API_URL = 'http://localhost:8080/api/bridge'
  // const API_URL = '/api/bridge';
  async function postData(url = '', data = {}, res = false) {
    // Default options are marked with *
    const response = await fetch(url, {
      method: 'POST', // *GET, POST, PUT, DELETE, etc.
      mode: 'cors', // no-cors, *cors, same-origin
      cache: 'no-cache', // *default, no-cache, reload, force-cache, only-if-cached
      credentials: 'same-origin', // include, *same-origin, omit
      headers: {
        'Content-Type': 'application/json'
        // 'Content-Type': 'application/x-www-form-urlencoded',
      },
      redirect: 'follow', // manual, *follow, error
      referrerPolicy: 'no-referrer', // no-referrer, *no-referrer-when-downgrade, origin, origin-when-cross-origin, same-origin, strict-origin, strict-origin-when-cross-origin, unsafe-url
      body: JSON.stringify(data) // body data type must match "Content-Type" header
    })
    if (response && res) {
      return response.json() // parses JSON response into native JavaScript objects
    }
    return { status: 'fail' }
  }

  const initialState = {
    is_playing: false,
    percent_complete: 0,
    paused: false,
    track_index: 0,
    now_playing: {
      artist: '',
      title: '',
      duration: '',
      filesize: 0,
      url: ''
    },
    queued: [
      {
        artist: '',
        title: '',
        duration: '',
        url: ''
      }
    ]
  }

  const yt3 = async () => {
    const res = await fetch(`${API_URL}/ctl/youtube/info`)
      .then((datas) => {
        return datas.json()
      })
      .then((dat) => {
        if (dat) {
          setState(dat)
        }
        return dat
      })
    return res
  }

  type DataType = typeof initialState

  const fetchFunc = async () => {
    const res = await yt3()
    return res
  }
  const options: APIPollingOptions<DataType> = {
    fetchFunc,
    initialState,
    delay: 1000
  }
  const currentPosition = useAPIPolling(options)

  return (
    <>
      <div
        style={{
          position: 'fixed',
          display: 'flex',
          bottom: botHeight - 50,
          right: 36,
          zIndex: 5
        }}
      >
        {/* <Button
          onClick={async () => {
            await yt3();
          }}
        >
          <BladeIcon name="Sync" />
        </Button> */}
        <ChangeYoutubeURLDialog
          youtubeURL={youtubeURL}
          setYoutubeURL={setYoutubeURL}
        />
        <IconButton onClick={() => setYoutubeExpanded(!youtubeExpanded)}>
          <QueueMusic />
        </IconButton>
      </div>
      <div
        style={{
          position: 'fixed',
          background:
            'linear-gradient(0deg, rgba(17,17,17,1) 0%, rgba(51,51,51,1) 35%, rgba(8,8,8,1) 100%), #282828',
          bottom: 0,
          left: 0,
          width: '100%',
          height: youtubeEnabled ? (youtubeExpanded ? 300 : 80) : 0,
          zIndex: 4
        }}
      >
        <div
          style={{
            display: 'flex',
            height: '100%',
            alignItems: 'center',
            flexWrap: 'wrap'
          }}
        >
          <div style={{ margin: '0 20px' }}>
            <Button
              disabled={state.track_index === 0}
              onClick={async () => {
                await postData(`${API_URL}/ctl/youtube/set`, {
                  action: 'previous'
                })
              }}
            >
              <BladeIcon name="SkipPrevious" />
            </Button>
            {!state.is_playing ? (
              <Button
                onClick={async () => {
                  await postData(`${API_URL}/ctl/youtube/set`, {
                    action: 'play'
                  })
                }}
              >
                <BladeIcon name="PlayArrowRounded" />
              </Button>
            ) : state.paused ? (
              <Button
                onClick={async () => {
                  await postData(`${API_URL}/ctl/youtube/set`, {
                    action: 'resume'
                  })
                }}
              >
                <BladeIcon name="PlayArrowRounded" />
              </Button>
            ) : (
              <Button
                onClick={async () => {
                  await postData(`${API_URL}/ctl/youtube/set`, {
                    action: 'pause'
                  })
                }}
              >
                <BladeIcon name="PauseRounded" />
              </Button>
            )}

            <Button
              disabled={state.queued.length - state.track_index < 1}
              onClick={async () => {
                await postData(`${API_URL}/ctl/youtube/set`, {
                  action: 'next'
                })
              }}
            >
              <BladeIcon name="SkipNext" />
            </Button>
          </div>
          <div>
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                height: '100%'
              }}
            >
              <Typography variant="h6">
                {state.now_playing.url !== ''
                  ? state.now_playing.title
                  : 'Youtube Integration'}
              </Typography>
              <div>
                <Typography variant="caption">
                  {state.now_playing.artist}
                </Typography>
                {state.now_playing.url === '' && (
                  <Typography variant="caption" color="textSecondary">
                    hacked by Blade
                  </Typography>
                )}
              </div>
            </div>
          </div>

          <div
            style={{
              width: '100%',
              maxWidth: 600,
              margin: '0px 60px -25px 60px'
            }}
          >
            <Slider
              style={{ width: '100%', maxWidth: 600 }}
              disabled
              min={0}
              max={100}
              value={currentPosition.percent_complete}
              step={0.01}
            />
            <div
              style={{
                flexGrow: 1,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                width: '100%',
                maxWidth: 600,
                marginTop: -15
              }}
            >
              <Typography variant="caption" color="textSecondary">
                0
              </Typography>
              <Typography variant="caption" color="textSecondary">
                {state.now_playing.duration}
              </Typography>
            </div>
          </div>
          {youtubeExpanded && (
            <div
              style={{
                flexBasis: '100%',
                background: '#111',
                height: 220,
                overflow: 'auto'
              }}
            >
              {state.queued.length > 0 &&
                state.queued.map((t: (typeof state.queued)[0], i: number) => (
                  <div
                    key={i}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      flexWrap: 'wrap',
                      borderBottom: '1px solid #333',
                      borderTop: i === 0 ? '1px solid #333' : 0,
                      backgroundColor:
                        i === state.track_index ? '#fff2' : '#fff0'
                    }}
                  >
                    <div style={{ margin: '0 20px' }}>
                      <Button
                        disabled={!state.is_playing}
                        onClick={() => {
                          window.open(t.url, '_blank')?.focus()
                        }}
                        color="primary"
                      >
                        <BladeIcon name="mdi:youtube" />
                      </Button>

                      <Button disabled>
                        <BladeIcon name="PlayArrowRounded" />
                      </Button>
                      <Button disabled>
                        <BladeIcon name="" />
                      </Button>
                    </div>
                    <div>
                      <Typography
                        variant="h6"
                        color={
                          i === state.track_index
                            ? 'textPrimary'
                            : 'textSecondary'
                        }
                      >
                        {t.title}
                      </Typography>
                      <div>
                        <Typography
                          variant="caption"
                          color={
                            i === state.track_index
                              ? 'textPrimary'
                              : 'textSecondary'
                          }
                        >
                          {t.artist}
                        </Typography>
                        <Typography variant="caption" color="textSecondary">
                          {' - '}({t.duration})
                        </Typography>
                      </div>
                    </div>
                  </div>
                ))}
            </div>
          )}
        </div>
      </div>
    </>
  )
}
export default YoutubeWidgetBar
