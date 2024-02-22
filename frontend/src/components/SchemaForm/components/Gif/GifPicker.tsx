import React, { useEffect, useState } from 'react'
import Dialog from '@mui/material/Dialog'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import TextField from '@mui/material/TextField'
import { Button, DialogActions, useTheme } from '@mui/material'
import fx from '../../../Icons/FX.svg'

interface Gif {
  name: string
  url: string
}

interface GifPickerProps {
  onChange: (_url: string) => void
}

const GifPicker: React.FC<GifPickerProps> = ({ onChange }: any) => {
  const theme = useTheme()
  const [gifs, setGifs] = useState<Gif[]>([])
  const [filter, setFilter] = useState('')
  const [open, setOpen] = useState(false)
  const [selectedGif, setSelectedGif] = useState<string | null>(null)

  const handleClickOpen = () => {
    setOpen(true)
  }

  const handleClose = () => {
    setOpen(false)
  }

  const baseUrl = 'https://assets.ledfx.app/gifs/'
  useEffect(() => {
    if (open)
      fetch(baseUrl)
        .then((response) => response.text())
        .then((data) => {
          const parser = new DOMParser()
          const doc = parser.parseFromString(data, 'text/html')
          const links = doc.querySelectorAll('pre a')
          const files = Array.from(links)
            .filter((link) => link.textContent?.endsWith('.gif'))
            .map((link: any) => ({
              name: link.textContent?.replace('.gif', ''),
              url: baseUrl + link.href.split('/').pop()
            }))
          setGifs(files)
        })
    // setGifs([
    //   {
    //     name: 'bruces1',
    //     url: 'https://assets.ledfx.app/gifs/bruces1.gif'
    //   },
    //   {
    //     name: 'cat-space',
    //     url: 'https://assets.ledfx.app/gifs/cat-space.gif'
    //   },
    //   {
    //     name: 'catfixed',
    //     url: 'https://assets.ledfx.app/gifs/catfixed.gif'
    //   },
    //   {
    //     name: 'dancing',
    //     url: 'https://assets.ledfx.app/gifs/dancing.gif'
    //   },
    //   {
    //     name: 'phoebe',
    //     url: 'https://assets.ledfx.app/gifs/phoebe.gif'
    //   },
    //   {
    //     name: 'snoopy',
    //     url: 'https://assets.ledfx.app/gifs/snoopy.gif'
    //   },
    //   {
    //     name: 'sponge',
    //     url: 'https://assets.ledfx.app/gifs/sponge.gif'
    //   },
    //   {
    //     name: 'zilla1',
    //     url: 'https://assets.ledfx.app/gifs/zilla1.gif'
    //   }
    // ])
  }, [open])

  return (
    <>
      <Button onClick={handleClickOpen} sx={{ alignSelf: 'center' }}>
        <img
          width={50}
          height="24px"
          src={fx}
          alt="wled"
          style={{
            filter: 'invert(1) brightness(2)',
            objectFit: 'cover'
          }}
        />
      </Button>
      <Dialog open={open} onClose={handleClose}>
        <DialogTitle>GIF Picker</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            sx={{ marginBottom: '20px', minWidth: '522px' }}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter GIFs..."
          />
          {gifs
            .filter((gif) => gif.name.includes(filter))
            .map((gif, i) => (
              // eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions
              <img
                key={gif.name}
                src={gif.url}
                alt={gif.name}
                style={{
                  height: '100px',
                  marginRight: '10px',
                  border: '2px solid',
                  cursor: 'pointer',
                  borderColor:
                    selectedGif === gif.url
                      ? theme.palette.primary.main
                      : 'transparent'
                }}
                tabIndex={i + 1}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleClose()
                  }
                }}
                onClick={() => {
                  if (selectedGif !== gif.url) {
                    setSelectedGif(gif.url)
                  } else {
                    setSelectedGif(null)
                  }
                  onChange(gif.url)
                  //   handleClose()
                }}
              />
            ))}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose}>OK</Button>
        </DialogActions>
      </Dialog>
    </>
  )
}

export default GifPicker
