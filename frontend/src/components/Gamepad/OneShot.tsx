import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  Slider,
  Stack
} from '@mui/material'
import { useState } from 'react'
import ReactGPicker from 'react-gcolor-picker'
import { Edit } from '@mui/icons-material'
import useStore from '../../store/useStore'
import BladeIcon from '../Icons/BladeIcon/BladeIcon'

const OneShot = ({
  setPayload,
  defaultColor,
  defaultRamp,
  defaultHold,
  defaultFate
}: any) => {
  const [color, setColor] = useState(defaultColor || '#fff')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [ramp, setRamp] = useState(defaultRamp || 10)
  const [hold, setHold] = useState(defaultHold || 200)
  const [fade, setFade] = useState(defaultFate || 2000)
  const colors = useStore((state) => state.colors)
  const handleClose = () => {
    setDialogOpen(false)
  }
  const handleSave = () => {
    setPayload({ color, ramp, hold, fade })
    setDialogOpen(false)
  }

  const defaultColors: any = {}
  Object.entries(colors.gradients.builtin).forEach(([k, g]) => {
    defaultColors[k] = g
  })
  Object.entries(colors.gradients.user).forEach(([k, g]) => {
    defaultColors[k] = g
  })
  Object.entries(colors.colors.builtin).forEach(([k, g]) => {
    defaultColors[k] = g
  })
  Object.entries(colors.colors.user).forEach(([k, g]) => {
    defaultColors[k] = g
  })
  return (
    <>
      {defaultColor ? (
        <Box
          onClick={() => setDialogOpen(true)}
          sx={{
            display: 'block',
            borderRadius: '4px',
            width: '2rem',
            height: '1rem',
            justifyContent: 'space-between',
            backgroundColor: defaultColor,
            cursor: 'pointer'
          }}
        />
      ) : (
        <Button variant="text" onClick={() => setDialogOpen(true)}>
          <Edit />
        </Button>
      )}
      <Dialog open={dialogOpen} onClose={handleClose} fullWidth>
        <DialogTitle alignItems="center" display="flex">
          <BladeIcon name="mdi:pistol" style={{ marginRight: 16 }} /> One Shot
        </DialogTitle>
        <DialogContent>
          <Stack
            direction="row"
            alignItems="flex-start"
            justifyContent="space-between"
            spacing={1}
          >
            <FormControl>
              <ReactGPicker
                colorBoardHeight={150}
                debounce
                debounceMS={300}
                format="hex"
                gradient={false}
                solid
                onChange={(c) => {
                  return setColor(c)
                }}
                popupWidth={288}
                showAlpha={false}
                value={color}
                defaultColors={Object.values(defaultColors)}
              />
            </FormControl>
            <Box sx={{ width: '40%' }}>
              <Slider
                value={ramp}
                onChange={(e, v) => setRamp(v as number)}
                valueLabelDisplay="auto"
                min={0}
                max={10000}
                step={10}
              />
              <Slider
                value={hold}
                onChange={(e, v) => setHold(v as number)}
                valueLabelDisplay="auto"
                min={0}
                max={10000}
                step={10}
              />
              <Slider
                value={fade}
                onChange={(e, v) => setFade(v as number)}
                valueLabelDisplay="auto"
                min={0}
                max={10000}
                step={10}
              />
              <Box
                sx={{
                  display: 'block',
                  marginTop: '2rem',
                  borderRadius: '0.5rem',
                  width: '100%',
                  height: '5rem',
                  justifyContent: 'space-between',
                  backgroundColor: color
                }}
              />
            </Box>
          </Stack>
          <code
            style={{
              display: 'block',
              margin: '1rem 0',
              padding: '1rem',
              background: '#333',
              color: '#ffffff'
            }}
          >
            {`{"color":"${color}","ramp":${ramp},"hold":${hold},"fade":${fade}}`}
          </code>
          <DialogActions>
            <Button onClick={handleClose}>Cancel</Button>
            <Button onClick={handleSave}>Save</Button>
          </DialogActions>
        </DialogContent>
      </Dialog>
    </>
  )
}
export default OneShot
