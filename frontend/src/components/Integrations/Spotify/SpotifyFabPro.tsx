import { Fab } from '@mui/material'
import { useState } from 'react'
import BladeIcon from '../../Icons/BladeIcon/BladeIcon'
import SpotifyWidgetPro from './Widgets/SpotifyWidgetPro/SpWidgetPro'

const SpotifyFabPro = ({ botHeight }: any) => {
  const [floatingWidget, setFloatingWidget] = useState(false)

  return (
    <>
      <div
        className="spotifyFab"
        style={{
          backgroundColor: '#0dbedc',
          position: 'fixed',
          bottom: botHeight + 105,
          right: 10,
          zIndex: 4
        }}
      >
        <Fab
          size="small"
          color="inherit"
          onClick={() => setFloatingWidget(!floatingWidget)}
          style={{
            position: 'fixed',
            bottom: botHeight + 115,
            right: 10,
            zIndex: 4,
            backgroundColor: '#1db954'
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
      </div>
      {floatingWidget && <SpotifyWidgetPro drag />}
    </>
  )
}

export default SpotifyFabPro
