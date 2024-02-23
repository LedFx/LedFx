import { WebPlaybackTrack } from './WebPlaybackTrack'

export type SpotifyState = {
  context: {
    uri: string | null // The URI of the context (can be null)
    metadata: any // Additional metadata for the context (can be null)
  }
  disallows: {
    // A simplified set of restriction controls for
    pausing: boolean // The current track. By default, these fields
    peeking_next: boolean // will either be set to false or undefined, which
    peeking_prev: boolean // indicates that the particular operation is
    resuming: boolean // allowed. When the field is set to `true`, this
    seeking: boolean // means that the operation is not permitted. For
    skipping_next: boolean // example, `skipping_next`, `skipping_prev` and
    skipping_prev: boolean // `seeking` will be set to `true` when playing an
  }
  loading: boolean
  duration: number
  paused: boolean // Whether the current track is paused.
  position: number // The position_ms of the current track.
  repeat_mode: number // The repeat mode. No repeat mode is 0,
  // repeat context is 1 and repeat track is 2.
  shuffle: boolean // True if shuffled, false otherwise.
  track_window: {
    current_track: WebPlaybackTrack // The track currently on local playback
    previous_tracks?: WebPlaybackTrack[] // Previously played tracks. Number can vary.
    next_tracks?: WebPlaybackTrack[] // Tracks queued next. Number can vary.
  }
}
