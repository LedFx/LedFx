/* eslint-disable no-console */
import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import { useContext, useEffect } from 'react'
import useStore from '../../../../../store/useStore'
import { getPlaylist } from '../../../../../utils/spotifyProxies'
import { SpotifyStateContext, SpStateContext } from '../../SpotifyProvider'
import useStyle, { CoverImage } from './SpWidgetPro.styles'

export default function SpTrack({ className }: any) {
  const classes = useStyle()

  const spotifyCtx = useContext(SpotifyStateContext)
  const spCtx = useContext(SpStateContext)
  const spotifyToken = useStore((state) => state.spotify.spotifyAuthToken)
  const setPlaylist = useStore((state) => state.setPlaylist)
  const title =
    spotifyCtx?.track_window?.current_track?.name ||
    spCtx?.item?.name ||
    'Not playing'
  const image =
    spotifyCtx?.track_window?.current_track?.album.images[0].url ||
    spCtx?.item?.album?.images[0].url ||
    'https://github.com/LedFx/LedFx/raw/main/icons/discord.png'
  const artist = spotifyCtx?.track_window?.current_track?.artists ||
    spCtx?.item?.artists || [{ name: 'on LedFx' }]

  useEffect(() => {
    const playlistUri =
      spotifyCtx?.context?.metadata?.uri || spCtx?.context?.uri
    if (playlistUri?.split(':')[1] === 'playlist') {
      getPlaylist(playlistUri.split(':')[2], spotifyToken).then((r) => {
        setPlaylist(r.items)
      })
    }
  }, [spotifyCtx?.context?.metadata?.uri, spCtx?.context?.uri])

  const album =
    spotifyCtx?.track_window?.current_track?.album?.name ||
    spCtx?.item?.album?.name ||
    ''
  return (
    <Box className={className}>
      <CoverImage className={classes.albumImg}>
        <img alt="album_image" src={image} />
      </CoverImage>
      <Box sx={{ ml: 1.5, minWidth: 0 }}>
        <Typography
          variant="body2"
          color="rgba(255,255,255,0.7)"
          fontSize={10}
          noWrap
        >
          {album}
        </Typography>
        <Typography noWrap>
          <b>{title}</b>
        </Typography>
        <Typography noWrap letterSpacing={-0.25} color="rgba(255,255,255,0.8)">
          {artist.length > 1
            ? artist.map((art: any) => art.name).join(',')
            : artist[0].name}
        </Typography>
      </Box>
    </Box>
  )
}
