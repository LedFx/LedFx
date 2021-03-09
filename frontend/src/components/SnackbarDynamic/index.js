import React from 'react';
import { useDispatch, useSelector } from 'react-redux';
import Snackbar from '@material-ui/core/Snackbar';
import MuiAlert from '@material-ui/lab/Alert';
import IconButton from '@material-ui/core/IconButton';
import { Icon } from '@material-ui/core';
import { clearSnackbar } from '../../modules/ui';

const Alert = props => <MuiAlert elevation={6} variant="filled" {...props} />;

const SnackbarDynamic = () => {
    const dispatch = useDispatch();

    const { dynSnackbarMessage, dynSnackbarOpen, dynSnackbarType } = useSelector(
        state => state.ui.snackbar
    );

    function handleClose() {
        dispatch(clearSnackbar());
    }

    return (
        <Snackbar
            anchorOrigin={{
                vertical: 'bottom',
                horizontal: 'center',
            }}
            open={dynSnackbarOpen}
            autoHideDuration={1000 + (dynSnackbarMessage || 0).length * 60}
            onClose={handleClose}
            aria-describedby="client-snackbar"
            action={[
                <IconButton key="close" aria-label="close" color="inherit" onClick={handleClose}>
                    <Icon>close</Icon>
                </IconButton>,
            ]}
        >
            <Alert severity={dynSnackbarType}>{dynSnackbarMessage}</Alert>
        </Snackbar>
    );
};

export default SnackbarDynamic;
