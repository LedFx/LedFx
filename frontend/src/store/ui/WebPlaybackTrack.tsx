export type WebPlaybackTrack = {
  uri: string // Spotify URI
  id: string | null // Spotify ID from URI (can be null)
  type: 'track' | 'episode' | 'ad' // Content type: can be "track", "episode" or "ad"
  media_type: 'audio' | 'video' // Type of file: can be "audio" or "video"
  name: string // Name of content
  is_playable: boolean // Flag indicating whether it can be played
  album: {
    uri: string // Spotify Album URI
    name: string
    images: { url: string }[]
  }
  artists: { uri: string; name: string }[]
}
