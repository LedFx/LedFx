/* eslint-disable no-console */
import { useState } from 'react'
import { Fab } from '@mui/material'

// import ChangeYoutubeURLDialog from './ChangeYoutubeURLDialog';
import BladeIcon from '../../Icons/BladeIcon/BladeIcon'
import YoutubeWidgetBar from './YoutubeWidgetBar'

const YoutubeWidget = ({
  youtubeEnabled,
  setYoutubeEnabled,
  youtubeExpanded,
  setYoutubeExpanded,
  youtubeURL,
  setYoutubeURL,
  setSpotifyEnabled,
  setSpotifyExpanded,
  botHeight
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

  const [state, setState] = useState(initialState)

  const yt1 = async () => {
    await postData(`${API_URL}/set/input/youtube`, { verbose: true })
  }
  const yt2 = async () => {
    await postData(`${API_URL}/add/output/local`, { verbose: true })
  }
  // const yt3 = async () => {
  //   const res = await fetch(`${API_URL}/ctl/youtube/info`)
  //     .then((datas) => {
  //       return datas.json();
  //     })
  //     .then((dat) => {
  //       if (dat) {
  //         setState(dat);
  //       }
  //       return dat;
  //     });
  //   return res;
  // };
  const yt4 = async () => {
    await postData(`${API_URL}/ctl/youtube/set`, {
      action: 'download',
      url: youtubeURL
    })
  }

  const initYoutube = async () => {
    yt1()
    setTimeout(() => {
      yt2()
    }, 10)
    // setTimeout(() => {
    //   yt3();
    // }, 20);
    setTimeout(() => {
      yt4()
    }, 30)
    // setTimeout(() => {
    //   yt3();
    // }, 100);
  }

  // useEffect(() => {
  //   setTimeout(() => {
  //     yt3();
  //   }, 100);
  // }, [youtubeURL]);

  return (
    <>
      <Fab
        size="small"
        color="secondary"
        onClick={() => {
          setSpotifyEnabled(false)
          setSpotifyExpanded(false)
          if (!youtubeEnabled) {
            initYoutube()
          }
          if (youtubeEnabled && youtubeExpanded) {
            setYoutubeExpanded(false)
          }
          setYoutubeEnabled(!youtubeEnabled)
        }}
        style={{
          position: 'fixed',
          bottom: botHeight + 115,
          right: 10,
          zIndex: 4
        }}
      >
        <BladeIcon
          name="mdi:youtube"
          style={{
            marginLeft: '50%',
            marginTop: '50%',
            transform: 'translate(-43%, -43%)',
            display: 'flex'
          }}
        />
      </Fab>
      {youtubeEnabled && (
        <YoutubeWidgetBar
          youtubeEnabled={youtubeEnabled}
          youtubeExpanded={youtubeExpanded}
          setYoutubeExpanded={setYoutubeExpanded}
          youtubeURL={youtubeURL}
          setYoutubeURL={setYoutubeURL}
          botHeight={botHeight}
          state={state}
          setState={setState}
        />
      )}
    </>
  )
}

export default YoutubeWidget
