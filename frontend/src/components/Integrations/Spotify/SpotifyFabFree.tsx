import { Fab } from '@mui/material'
import BladeIcon from '../../Icons/BladeIcon/BladeIcon'
import SpotifyWidgetFree from './Widgets/SpotifyWidgetFree/SpotifyWidgetFree'

const SpotifyFabFree = ({
  spotifyEnabled,
  setSpotifyEnabled,
  spotifyExpanded,
  setSpotifyExpanded,
  spotifyURL,
  setSpotifyURL,
  setYoutubeExpanded,
  setYoutubeEnabled,
  botHeight
}: any) => {
  return (
    <>
      <Fab
        size="small"
        color="secondary"
        onClick={() => {
          setYoutubeEnabled(false)
          setYoutubeExpanded(false)
          if (spotifyEnabled && spotifyExpanded) {
            setSpotifyExpanded(false)
          }
          setSpotifyEnabled(!spotifyEnabled)
        }}
        style={{
          position: 'fixed',
          bottom: botHeight + 65,
          right: 10,
          zIndex: 4
        }}
      >
        <BladeIcon
          name="mdi:spotify"
          style={{
            marginLeft: '50%',
            marginTop: '50%',
            transform: 'translate(-43%, -43%)',
            display: 'flex'
          }}
        />
      </Fab>
      {spotifyEnabled && (
        <SpotifyWidgetFree
          spotifyEnabled={spotifyEnabled}
          spotifyExpanded={spotifyExpanded}
          setSpotifyExpanded={setSpotifyExpanded}
          spotifyURL={spotifyURL}
          setSpotifyURL={setSpotifyURL}
        />
      )}
    </>
  )
}

export default SpotifyFabFree
