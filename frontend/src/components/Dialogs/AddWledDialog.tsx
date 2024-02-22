import { styled } from '@mui/material/styles'
import {
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Button
} from '@mui/material'
import {
  DataGrid,
  GridColDef,
  GRID_CHECKBOX_SELECTION_COL_DEF,
  useGridApiRef
} from '@mui/x-data-grid'
import { useMemo } from 'react'
import useStore from '../../store/useStore'
// import nameToIcon from '../../utils/nameToIcon'

const PREFIX = 'AddWledDialog'

const classes = {
  wrapper: `${PREFIX}-wrapper`
}

const StyledDialog = styled(Dialog)(({ theme }) => ({
  [`& .${classes.wrapper}`]: {
    minWidth: '200px',
    padding: '16px 1.2rem 6px 1.2rem',
    border: '1px solid #999',
    borderRadius: '10px',
    position: 'relative',
    margin: '1rem 0',
    display: 'flex',
    alignItems: 'center',
    '@media (max-width: 580px)': {
      width: '100%',
      margin: '0.5rem 0'
    },
    '& > label': {
      top: '-0.7rem',
      display: 'flex',
      alignItems: 'center',
      left: '1rem',
      padding: '0 0.3rem',
      position: 'absolute',
      fontVariant: 'all-small-caps',
      fontSize: '0.9rem',
      letterSpacing: '0.1rem',
      backgroundColor: theme.palette.background.paper,
      boxSizing: 'border-box'
    }
  }
}))

const AddWledDialog = () => {
  const addMoreWleds = useStore((state) => state.dialogs.addWled.open)
  const open = addMoreWleds.length > 0 || false
  const apiRef = useGridApiRef()
  const getDevices = useStore((state) => state.getDevices)
  const getVirtuals = useStore((state) => state.getVirtuals)
  const addDevice = useStore((state) => state.addDevice)
  const setAddWLed = useStore((state) => state.setAddWLed)

  const handleClose = () => {
    setAddWLed([])
  }
  const handleAddDevices = () => {
    const defaultModel = {
      center_offset: 0,
      refresh_rate: 64,
      sync_mode: 'DDP',
      timeout: 1,
      create_segments: true,
      icon_name: 'wled'
    }

    // eslint-disable-next-line @typescript-eslint/no-unused-vars, no-unused-vars
    // let icon = 'wled'
    const promises: any = apiRef.current.getSelectedRows().forEach((row) => {
      // if row.name is part of a key of nametoicon then return the value else 'wled'

      // Object.keys(nameToIcon).some((key) => {
      //   if (row.name.toLowerCase().includes(key.toLowerCase())) {
      //     icon = (nameToIcon as any)[key]
      //     return true
      //   }
      //   return false
      // })
      return addDevice({
        type: 'wled',
        config: {
          ...row,
          ...defaultModel
          // icon_name: icon
        }
      })
    })

    Promise.all(promises)
      .then((results) => {
        if (results.every((res) => res !== 'failed')) {
          getDevices()
          getVirtuals()
        }
      })
      .catch((_error) => {
        // console.log('Error: ', error)
      })
      .finally(() => {
        handleClose()
      })
  }

  const col: GridColDef[] = [
    { field: 'name', headerName: 'Name', width: 130 },
    { field: 'ip_address', headerName: 'IP', width: 130 }
  ]

  const columns = useMemo(
    () => [
      ...col,
      {
        ...GRID_CHECKBOX_SELECTION_COL_DEF,
        width: 100
      }
    ],
    [col]
  )
  return (
    <StyledDialog
      open={open}
      onClose={handleClose}
      aria-labelledby="form-dialog-title"
    >
      <DialogTitle id="form-dialog-title">Add more WLEDs to LedFx</DialogTitle>
      <DialogContent>
        <DataGrid
          apiRef={apiRef}
          rows={addMoreWleds}
          getRowId={(row) => row.ip_address}
          columns={columns}
          checkboxSelection
          hideFooter
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} color="primary">
          Cancel
        </Button>
        <Button onClick={handleAddDevices} color="primary">
          Add
        </Button>
      </DialogActions>
    </StyledDialog>
  )
}

export default AddWledDialog
