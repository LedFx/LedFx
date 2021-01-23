import React from 'react';
import { useDispatch, useSelector } from 'react-redux';
import Snackbar from '@material-ui/core/Snackbar';
import MuiAlert from '@material-ui/lab/Alert';
import IconButton from '@material-ui/core/IconButton';
import { Icon } from '@material-ui/core';
import { clearSnackbar } from '../../modules/ui';

const Alert = props => <MuiAlert elevation={6} variant="filled" {...props} />;

const SnackbarDynamic = ({ type = 'error' }) => {
    const dispatch = useDispatch();

    const { successSnackbarMessage, successSnackbarOpen } = useSelector(state => state.ui);

    function handleClose() {
        dispatch(clearSnackbar());
    }

    return (
        <Snackbar
            anchorOrigin={{
                vertical: 'bottom',
                horizontal: 'center',
            }}
            open={successSnackbarOpen}
            autoHideDuration={1000 + (successSnackbarMessage || 0).length * 60}
            onClose={handleClose}
            aria-describedby="client-snackbar"
            action={[
                <IconButton key="close" aria-label="close" color="inherit" onClick={handleClose}>
                    <Icon>close</Icon>
                </IconButton>,
            ]}
        >
            <Alert severity={type}>{successSnackbarMessage}</Alert>
        </Snackbar>
    );
};

export default SnackbarDynamic;
