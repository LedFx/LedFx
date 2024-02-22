import { IconButton } from '@mui/material'
import { QueueMusic } from '@mui/icons-material'
import SpotifyChangeURLDialog from './SpotifyChangeURLDialog'

const SpotifyWidgetFree = ({
  spotifyEnabled,
  spotifyExpanded,
  setSpotifyExpanded,
  spotifyURL,
  setSpotifyURL
}: any) => {
  return (
    <>
      <div
        style={{
          position: 'fixed',
          display: 'flex',
          bottom: spotifyExpanded ? 258 : 38,
          right: 36,
          zIndex: 2
        }}
      >
        <SpotifyChangeURLDialog
          spotifyURL={spotifyURL}
          setSpotifyURL={setSpotifyURL}
        />
        <IconButton onClick={() => setSpotifyExpanded(!spotifyExpanded)}>
          <QueueMusic />
        </IconButton>
      </div>
      <iframe
        title="Spotify Embed Player"
        src={`${spotifyURL
          .split('?')[0]
          .replace('.com/embed/', '.com/')
          .replace('.com/', '.com/embed/')}?theme=0`}
        width="100%"
        height={spotifyEnabled ? (spotifyExpanded ? 300 : 80) : 0}
        style={{ position: 'fixed', bottom: 0, left: 0 }}
        frameBorder="0"
        /* eslint-disable-next-line react/no-unknown-property */
        allowTransparency
        allow="encrypted-media"
      />
    </>
  )
}

export default SpotifyWidgetFree
