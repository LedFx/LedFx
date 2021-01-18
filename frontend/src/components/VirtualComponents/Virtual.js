import React from 'react'
import { useDispatch, useSelector } from "react-redux"
import PopoverNew from 'components/VirtualComponents/PopoverNew'
import Grid from '@material-ui/core/Grid'
import Card from '@material-ui/core/Card'
import Typography from '@material-ui/core/Typography'
import CardContent from '@material-ui/core/CardContent'
import EditIcon from '@material-ui/icons/Edit'
import CheckIcon from '@material-ui/icons/Check'
import AddSegmentDialog from 'components/VirtualComponents/DialogAddSegment'
import VirtualComponents from 'components/VirtualComponents'
import PopoverSure from './PopoverSure'

function Virtual({ v, setSnackbarState }) {

  const dispatch = useDispatch()
  const virtuals = useSelector(state => state.virtuals.list)
  const deviceList = useSelector(state => state.devices.list)
  const allPixels = virtuals.filter(vi => vi.name === v.name).map(vir => vir.items && vir.items.length > 0 && vir.items.map(d => d.led_end - d.led_start + 1).reduce((sum, part) => sum + part))[0]

  const deleteVirtual = (virtual) => {
    dispatch({ type: 'virtuals/VIRTUAL_DELETE', payload: virtual })
  }
  const changeNameVirtual = (newName) => {
    if (virtuals.find(e => e.name === newName.new)) {
      setSnackbarState({ open: true, message: "Name already existing! Please choose a different one.", type: 'warning' })
    } else {
      dispatch({ type: 'virtuals/VIRTUAL_RENAME', payload: { old: newName.old, new: newName.new } })
      setSnackbarState({ open: true, message: "Virtual Device renamed", type: 'success' })
    }
  }

  return (
    <Card style={{ marginBottom: '2em' }}>
      <CardContent>
        <Grid container direction="row" spacing={1} justify="space-between">
          <Grid item xs="auto" style={{ display: 'flex' }}>
            <Typography variant="h5">{v.name}</Typography>
            <PopoverNew old={v.name} buttonText="" onSubmit={changeNameVirtual} variant="text" buttonIcon={<EditIcon />} submitIcon={<CheckIcon />} />
            <PopoverSure onDeleteVitem={() => deleteVirtual(v.name)} color="primary" variant="text" listItem={v.name} />
          </Grid>
          <Grid item xs="auto">
            <Typography variant="body1" color="textSecondary">
              Total Pixels: {allPixels}
            </Typography>
          </Grid>
          <Grid item>
            <AddSegmentDialog deviceList={deviceList} virtual={v.name} />
          </Grid>
        </Grid>
        {v.items && v.items.length > 0 && <VirtualComponents
          items={v.items}
          virtual={v}
        />}
      </CardContent>
    </Card>
  )
}

export default Virtual
