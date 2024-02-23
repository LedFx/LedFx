/* eslint-disable jsx-a11y/click-events-have-key-events */
/* eslint-disable jsx-a11y/no-static-element-interactions */
import React, { useState, FC, useCallback, useEffect } from 'react'
import Dialog from '@mui/material/Dialog'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import {
  Box,
  Button,
  DialogActions,
  Slider,
  TextField,
  Typography,
  useTheme
} from '@mui/material'
import { Colorize } from '@mui/icons-material'
import useStore from '../../../../store/useStore'

// interface Gif {
//   name: string
//   url: string
// }

interface GifFramePickerProps {
  onChange: (_url: string) => void
  model: any
}

const GifFramePicker: FC<GifFramePickerProps> = ({
  onChange,
  model
}: GifFramePickerProps) => {
  const theme = useTheme()
  const [open, setOpen] = useState(false)
  // const [selectedGif, setSelectedGif] = useState<string | null>(null)
  // console.log(model.beat_frames)
  const handleClickOpen = () => {
    setOpen(true)
  }

  const handleClose = () => {
    setOpen(false)
  }

  const [imageData, setImageData] = useState<string[]>([])
  const getGifFrames = useStore((state) => state.getGifFrames)
  const [currentFrame, setCurrentFrame] = useState(0)
  const fetchImage = useCallback(async (ic: string) => {
    const result = await getGifFrames(ic)
    // console.log(result)
    setImageData(result.frames)
  }, [])

  useEffect(() => {
    fetchImage(model.image_location)
  }, [])
  // useEffect(() => {
  //   if (open)
  //     fetch(baseUrl)
  //       .then((response) => response.text())
  //       .then((data) => {
  //         const parser = new DOMParser()
  //         const doc = parser.parseFromString(data, 'text/html')
  //         const links = doc.querySelectorAll('pre a')
  //         const files = Array.from(links)
  //           .filter((link) => link.textContent?.endsWith('.gif'))
  //           .map((link: any) => ({
  //             name: link.textContent?.replace('.gif', ''),
  //             url: baseUrl + link.href.split('/').pop()
  //           }))
  //         setGifs(files)
  //       })
  // }, [open])

  return (
    <>
      <Button onClick={handleClickOpen} sx={{ alignSelf: 'center' }}>
        <Colorize />
      </Button>
      <Dialog
        open={open}
        onClose={handleClose}
        PaperProps={{ sx: { width: '100%' } }}
      >
        <DialogTitle>GIF Frame Picker</DialogTitle>
        <DialogContent sx={{ minWidth: 332, width: '100%' }}>
          {imageData && (
            <>
              <TextField
                label="Selected Beat Frames"
                value={model.beat_frames}
                onChange={(e) => onChange(e.target.value)}
                sx={{ margin: '20px 0', minWidth: '522px' }}
              />
              <Box>
                <Typography variant="caption" color="GrayText">
                  Click on image to select/deselect
                </Typography>
              </Box>
              <div
                style={{
                  height: 300,
                  width: 'min(100% - 32px, 520px)',
                  minWidth: 300,
                  maxWidth: 520,
                  backgroundSize: 'contain',
                  backgroundRepeat: 'no-repeat',
                  backgroundPosition: 'center',
                  backgroundImage: `url("data:image/png;base64,${imageData[currentFrame || 0]}")`,
                  border: '4px solid',
                  cursor: 'pointer',
                  borderColor: model.beat_frames
                    .split(' ')
                    .includes(currentFrame.toString())
                    ? theme.palette.primary.main
                    : '#9999'
                }}
                title="SceneImage"
                onClick={() => {
                  let output = ''
                  if (
                    model.beat_frames
                      .split(' ')
                      .includes(currentFrame.toString())
                  ) {
                    output = model.beat_frames
                      .split(' ')
                      .filter((b: string) => b !== currentFrame.toString())
                      .join(' ')
                  } else {
                    output = model.beat_frames
                      .concat([` ${currentFrame.toString()}`])
                      .split(' ')
                      .sort(
                        (a: string, b: string) =>
                          parseInt(a, 10) - parseInt(b, 10)
                      )
                      .join(' ')
                  }
                  onChange(output)
                }}
              />
              <Box sx={{ maxWidth: 520, mt: 2 }}>
                <Slider
                  defaultValue={0}
                  aria-label="Default"
                  valueLabelDisplay="auto"
                  step={1}
                  marks={model.beat_frames.split(' ').map((b: number) => ({
                    value: b,
                    label: b.toString()
                  }))}
                  min={0}
                  max={imageData.length - 1 || 0}
                  onChange={(e, v) => {
                    setCurrentFrame(v as number)
                    // onChange(imageData[v as number])
                  }}
                />
              </Box>
            </>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose}>OK</Button>
        </DialogActions>
      </Dialog>
    </>
  )
}

export default GifFramePicker
