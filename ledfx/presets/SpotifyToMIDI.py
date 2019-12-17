import requests
import asyncio
import spotify
#Possible MIDI lib: music21, py-midi, midi, mido (https://pypi.org/project/py-midi/)

# ------------------------------------------------------------------------------- #
#Settings
Range_ms = '10000' #Plus or minus 10 seconds time range to set off trigger
OAuthSpotifyToken = 'BQD-frXd55B3WgNKNA6CgMDhYpS2JD1cRjCQurL_zFbhPVcWsHVW_5BFL1M-7DWY6B18FUgn1by54D3ZjN76yeX9MZEi7LMP7LCzNSa4rtrsjVDAfh4DaA90hQWci3Qlod4zH3xcn6hH4X0FAwD52ZjpOe6OnQ'
pollSpotify_ms = '10000' #10 second interval to GET Spotify API data

# ------------------------------------------------------------------------------- #
#Song & Time Table
#GET via LedFx API "Presets Management" Table - to be developed.
#Convert trigger time mm:ss to ms
#Update "Presets Management" Table
#If matches any line of the CSV, then send MIDI or Keyboard - line 39

# ------------------------------------------------------------------------------- #
#Spotify Token
#If Spotify token is valid, then use token.
#if Spofity token is NOT valid, then request token & save token with timestamp.
client = spotify.Client('7658827aea6f47f98c8de593f1491da5', 'somesecret')
    async def main():
        user = await client.user_from_token('sometoken')
        details = await user.currently_playing()
        print(details)    
    if __name__ == '__main__':
        asyncio.get_event_loop().run_until_complete(main())

# ------------------------------------------------------------------------------- #
#Spotify API - https://developer.spotify.com/documentation/web-api/reference-beta/
#GET currently playing song and time.
spotify.current_player()
#current_player(*, market: Optional[str] = None) → Awaitable[T_co]
#requests.get(https://api.spotify.com/v1/me/player/currently-playing,)
#"progress_ms": 11894,

# ------------------------------------------------------------------------------- #
#If Spotify song, then send output MIDI or Keyboard (defined in SpotifyTriggerDB)
    #Example of sending MIDI: 
#progress_ms triggered to mm:ss
#print, song artist & name, with triggered mm:ss, and output triggered
# ------------------------------------------------------------------------------- #

