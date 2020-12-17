import React, { useEffect, useState } from 'react'
import Grid from '@material-ui/core/Grid'
import { useDispatch, useSelector } from "react-redux"
import MuiAlert from '@material-ui/lab/Alert'
import Snackbar from '@material-ui/core/Snackbar'
import Button from '@material-ui/core/Button'
import PopoverNew from 'components/VirtualComponents/PopoverNew'
import Virtual from 'components/VirtualComponents/Virtual'
import { fetchDeviceList } from 'modules/devices'
import { getAsyncVirtuals } from 'modules/virtuals'
import SaveIcon from '@material-ui/icons/Save'
import * as virtualsProxies from 'proxies/virtuals'
import InputLabel from '@material-ui/core/InputLabel';
import MenuItem from '@material-ui/core/MenuItem';
import FormControl from '@material-ui/core/FormControl';
import Select from '@material-ui/core/Select';

function Alert(props) {
    return <MuiAlert elevation={6} variant="filled" {...props} />
}

const VirtualsView = () => {
    const virtuals = useSelector(state => state.virtuals.list)
    const dispatch = useDispatch()
    const [snackbarState, setSnackbarState] = useState({ open: false, message: '', type: 'error' })

    const [age, setAge] = useState(window.localStorage.getItem("blade") || 0);

    const addNewVirtual = (newName) => {
        if (virtuals.find(e => e.name === newName.new)) {
            setSnackbarState({ ...snackbarState, open: true, message: "Name already existing! Please choose a different one.", type: 'warning' })
        } else {
            dispatch({ type: 'virtuals/VIRTUAL_ADD', payload: newName })
            setSnackbarState({ ...snackbarState, open: true, message: "Virtual Device added", type: 'success' })
        }
    }

    const handleClose = () => {
        setSnackbarState({ ...snackbarState, open: false })
    }
    const changeTheme = (event) => {
        setAge(event.target.value)
        window.localStorage.setItem("blade", event.target.value)
        window.location = window.location.href
    }
    useEffect(() => {
        dispatch(fetchDeviceList())
        dispatch(getAsyncVirtuals())
    }, [dispatch])

    return (
        <Grid container spacing={2}>
            <Grid item xs={12} md={12}>
                <FormControl >
                    <InputLabel id="theme-selector">Theme</InputLabel>
                    <Select
                        labelId="theme-selector"
                        id="theme-select"
                        value={age}
                        onChange={changeTheme}
                    >
                        <MenuItem value={0}>Default</MenuItem>
                        <MenuItem value={1}>Dark</MenuItem>
                        <MenuItem value={2}>Blade</MenuItem>
                        <MenuItem value={3}>BladeDark</MenuItem>
                    </Select>
                </FormControl>
                {virtuals.map((v, i) => <Virtual v={v} key={i} setSnackbarState={setSnackbarState} />)}
                <div style={{ display: "flex", marginTop: '1em', justifyContent: 'space-between' }}>
                    <PopoverNew onSubmit={addNewVirtual} />
                    <Button variant="contained" style={{ margin: "8px" }} color="primary" onClick={() => {
                        virtualsProxies.setVirtuals({ virtuals: { list: virtuals } })
                    }}>
                        Save
                        <SaveIcon style={{ marginLeft: '0.5em' }} />
                    </Button>
                </div>
            </Grid>
            <Snackbar
                anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
                autoHideDuration={1000 + snackbarState.message.length * 60}
                open={snackbarState.open}
                onClose={handleClose}
                key={'bottomcenter'}
            >
                <Alert severity={snackbarState.type}>{snackbarState.message}</Alert>
            </Snackbar>
        </Grid >
    )
}

export default VirtualsView