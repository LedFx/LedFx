import React from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button } from '@material-ui/core';

const PleaseUpdateDialog = ({ open, onClose }) => {
    return (
        <Dialog open={open} onClose={onClose}>
            <DialogTitle>Please Update Manually</DialogTitle>
            <DialogContent>
                <p>You are operating on a very old version of LedFx that we cannot automatically update anymore.</p>
                <p>Please back up your configuration (on Windows it is located at %appdata%\.ledfx) and uninstall the current version of LedFx. </p>
                <p>Once this is done you can <a href="https://download.ledfx.app" target='_blank' rel="noopener noreferrer">download the new version.</a></p>
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose} color="primary">
                    OK
                </Button>
            </DialogActions>
        </Dialog>
    );
};

export default PleaseUpdateDialog;
