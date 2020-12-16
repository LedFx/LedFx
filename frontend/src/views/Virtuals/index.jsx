import React, { useEffect, useState } from 'react';
import Grid from '@material-ui/core/Grid';
import { useDispatch, useSelector } from "react-redux";
import MuiAlert from '@material-ui/lab/Alert';
import Snackbar from '@material-ui/core/Snackbar';
import PopoverNew from 'components/VirtualComponents/PopoverNew';
import Virtual from 'components/VirtualComponents/Virtual';
import { fetchDeviceList } from 'modules/devices';

function Alert(props) {
    return <MuiAlert elevation={6} variant="filled" {...props} />;
}

const VirtualsView = () => {

    const virtuals = useSelector(state => state.virtuals.list)
    const dispatch = useDispatch();

    const [snackbarState, setSnackbarState] = useState({ open: false, message: '', type: 'error' });

    const addNewVirtual = (newName) => {
        if (virtuals.find(e => e.name === newName.new)) {
            setSnackbarState({ ...snackbarState, open: true, message: "Name already existing! Please choose a different one.", type: 'warning' });
        } else {
            dispatch({ type: 'virtuals/VIRTUAL_ADD', payload: newName })
            setSnackbarState({ ...snackbarState, open: true, message: "Virtual Device added", type: 'success' });
        }
    }

    const handleClose = () => {
        setSnackbarState({ ...snackbarState, open: false });
    };


    useEffect(() => {
        dispatch(fetchDeviceList())
    }, [dispatch])

    return (
        <Grid container spacing={2}>
            <Grid item xs={12} md={12}>
                {virtuals.map((v, i) => <Virtual v={v} key={i} />)}
                <PopoverNew onSubmit={addNewVirtual} />

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
    );
}

export default VirtualsView