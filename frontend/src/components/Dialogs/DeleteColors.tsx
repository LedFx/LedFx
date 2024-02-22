import { useState } from 'react'
import {
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle
} from '@mui/material'
import * as React from 'react'
import OutlinedInput from '@mui/material/OutlinedInput'
import InputLabel from '@mui/material/InputLabel'
import MenuItem from '@mui/material/MenuItem'
import FormControl from '@mui/material/FormControl'
import ListItemText from '@mui/material/ListItemText'
import Select from '@mui/material/Select'
import { useTheme } from '@mui/material/styles'
import useStore from '../../store/useStore'

const ITEM_HEIGHT = 48
const ITEM_PADDING_TOP = 8

const DeleteColorsDialog = ({
  dialogOpen,
  setDialogOpen
}: {
  dialogOpen: boolean
  setDialogOpen: React.Dispatch<React.SetStateAction<boolean>>
}) => {
  const theme = useTheme()
  const MenuProps = {
    PaperProps: {
      style: {
        maxHeight: ITEM_HEIGHT * 4.5 + ITEM_PADDING_TOP,
        width: 250,
        background: theme.palette.background.paper
      }
    }
  }
  const [colorsToDelete, setColorsToDelete] = useState<string[]>([])

  const handleChange = (event: any) => {
    const {
      target: { value }
    } = event
    setColorsToDelete(
      // On autofill we get a the stringified value.
      typeof value === 'string' ? value.split(',') : value
    )
  }

  const colors = useStore((state) => state.colors)
  const deleteColors = useStore((state) => state.deleteColors)
  const getColors = useStore((state) => state.getColors)

  const handleClose = () => {
    setDialogOpen(false)
  }

  const handleDelete = () => {
    deleteColors(colorsToDelete).then(() => getColors())
    setColorsToDelete([])
    setDialogOpen(false)
  }

  return (
    <Dialog
      PaperProps={{
        sx: {
          background: theme.palette.background.paper,
          color: theme.palette.text.primary
        }
      }}
      open={dialogOpen}
      disableEscapeKeyDown
      onClose={handleClose}
      aria-labelledby="form-dialog-title"
    >
      <DialogTitle id="form-dialog-title">
        Delete user-defined colors/gradients
      </DialogTitle>
      <DialogContent>
        <FormControl
          sx={{
            m: 1,
            width: 300,
            '&&& fieldset, &&& fieldset:hover': {
              borderColor: theme.palette.text.primary
            }
          }}
        >
          <InputLabel
            sx={{ '&&&': { color: theme.palette.text.primary } }}
            id="demo-multiple-checkbox-label"
          >
            Select to delete
          </InputLabel>
          <Select
            labelId="demo-multiple-checkbox-label"
            id="demo-multiple-checkbox"
            multiple
            value={colorsToDelete}
            onChange={handleChange}
            input={
              <OutlinedInput
                color="primary"
                label="To be deleted"
                sx={{ '&&&': { color: theme.palette.text.primary } }}
              />
            }
            renderValue={(selected) => selected.join(', ')}
            MenuProps={MenuProps}
          >
            {colors.colors &&
              colors.gradients &&
              [
                ...Object.keys(colors.colors.user),
                ...Object.keys(colors.gradients.user)
              ].map((color) => (
                <MenuItem
                  key={color}
                  value={color}
                  sx={{
                    background: theme.palette.background.paper,
                    color: theme.palette.text.primary
                  }}
                >
                  <Checkbox
                    color="primary"
                    checked={colorsToDelete.indexOf(color) > -1}
                  />
                  <ListItemText primary={color} />
                  <div
                    style={{
                      width: 150,
                      height: 50,
                      background:
                        colors.colors.user[color] ||
                        colors.gradients.user[color]
                    }}
                  />
                </MenuItem>
              ))}
          </Select>
        </FormControl>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Cancel</Button>
        <Button onClick={handleDelete}>Delete</Button>
      </DialogActions>
    </Dialog>
  )
}

export default DeleteColorsDialog
