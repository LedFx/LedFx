import React from 'react'
import Button from '@mui/material/Button'
import TextField from '@mui/material/TextField'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogContentText from '@mui/material/DialogContentText'
import DialogTitle from '@mui/material/DialogTitle'
import IconButton from '@mui/material/IconButton'
import { Language } from '@mui/icons-material'

export default function SpotifyChangeURLDialog({
  style,
  spotifyURL,
  setSpotifyURL
}: any) {
  const [open, setOpen] = React.useState(false)
  const [url, setUrl] = React.useState(spotifyURL)

  const handleClickOpen = () => {
    setOpen(true)
  }
  const handleClose = (_e: any) => {
    setOpen(false)
  }
  const handleSave = (_e: any) => {
    setSpotifyURL(url)
    setOpen(false)
  }

  return (
    <div>
      <IconButton onClick={handleClickOpen} style={style}>
        <Language />
      </IconButton>
      <Dialog
        open={open}
        onClose={handleClose}
        aria-labelledby="form-dialog-title"
      >
        <DialogTitle id="form-dialog-title">Spotify URL</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Right-click a Playlist/Track/... in spotify and select share, copy
            link and paste it here
          </DialogContentText>
          <TextField
            autoFocus
            margin="dense"
            id="url"
            label="URL"
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            fullWidth
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose} color="primary">
            Cancel
          </Button>
          <Button onClick={handleSave} color="primary">
            Change
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  )
}
