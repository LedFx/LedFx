import { useEffect, useState } from 'react'
import {
  TextField,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Button,
  Typography
} from '@mui/material'
import useStore from '../../../store/useStore'

const AddSceneDialog = () => {
  const [name, setName] = useState('')
  const [overwrite, setOverwrite] = useState(false)
  const [invalid, setInvalid] = useState(false)

  const addScene = useStore((state) => state.addScene)
  const getScenes = useStore((state) => state.getScenes)
  const scenes = useStore((state) => state.scenes)
  const open = useStore((state) => state.dialogs.addScene?.open || false)

  const setDialogOpenAddScene = useStore((state) => state.setDialogOpenAddScene)
  useEffect(() => {
    setInvalid(false)
  }, [])

  const handleClose = () => {
    setDialogOpenAddScene(false)
  }
  const handleAddScene = () => {
    if (!invalid) {
      addScene(name).then(async () => {
        const newScenes = await getScenes()
        const sceneId = Object.keys(newScenes).find(
          (s) => newScenes[s].name === name
        )
        setName('')
        if (sceneId)
          setDialogOpenAddScene(true, true, sceneId, newScenes[sceneId])
      })
    }
  }

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      aria-labelledby="form-dialog-title"
    >
      <DialogTitle id="form-dialog-title">Add Scene</DialogTitle>
      <DialogContent>
        <Typography mb={2}>
          Save all active effects of all devices with their settings into one
          scene.
        </Typography>
        <TextField
          autoFocus
          margin="dense"
          id="name"
          label="Name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleAddScene()}
          onBlur={(e) => {
            setOverwrite(
              Object.keys(scenes).indexOf(e.target.value.toLowerCase()) > -1
            )
          }}
          error={overwrite}
          helperText={overwrite && 'Scene already existing!'}
          required
          fullWidth
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Cancel</Button>
        <Button onClick={handleAddScene}>
          {overwrite ? 'Overwrite' : 'Add & Configure'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

export default AddSceneDialog
