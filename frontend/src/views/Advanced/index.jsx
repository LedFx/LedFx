import React, { useState } from 'react';
import Grid from '@material-ui/core/Grid';
import MuiAlert from '@material-ui/lab/Alert';
import Snackbar from '@material-ui/core/Snackbar';
import { Button, Divider } from '@material-ui/core';

import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import CardHeader from '@material-ui/core/CardHeader';

import Check from '@material-ui/icons/Check';
import Warning from '@material-ui/icons/Warning';
import Info from '@material-ui/icons/Info';

import LogCard from './LogCard';
import ControlsCard from './ControlsCard';
import ThemesCard from './ThemesCard';
import ConfigEditor from './ConfigEditor';

function Alert(props) {
    return <MuiAlert elevation={6} variant="filled" {...props} />;
}

const AdvancedView = () => {
    const [snackbarState, setSnackbarState] = useState({ open: false, message: '', type: 'error' });

    const handleClose = () => {
        setSnackbarState({ ...snackbarState, open: false });
    };

    return (
        <Grid container spacing={2}>
            <Grid item xs={12} md={12}>
                <ThemesCard />
                <Divider style={{ margin: '2rem 0' }} />
                <LogCard />
                <Divider style={{ margin: '2rem 0' }} />
                {window.localStorage.getItem('BladeMod') > 1 && (
                    <>
                        <ControlsCard />
                        <Divider style={{ margin: '2rem 0' }} />
                        <ConfigEditor />
                        <Divider style={{ margin: '2rem 0' }} />
                        <Card>
                            <CardHeader title="DevButtons" subheader="for development" />
                            <CardContent>
                                <Button
                                    size="small"
                                    startIcon={<Warning />}
                                    variant="contained"
                                    style={{ marginRight: '10px' }}
                                    onClick={() => {
                                        setSnackbarState({
                                            ...snackbarState,
                                            message: 'TEST ERROR',
                                            open: true,
                                        });
                                    }}
                                >
                                    Error Message
                                </Button>
                                <Button
                                    size="small"
                                    startIcon={<Check />}
                                    variant="contained"
                                    style={{ marginRight: '10px' }}
                                    onClick={() => {
                                        setSnackbarState({
                                            ...snackbarState,
                                            message: 'TEST SUCCESS',
                                            open: true,
                                            type: 'success',
                                        });
                                    }}
                                >
                                    Success Message
                                </Button>
                                <Button
                                    size="small"
                                    startIcon={<Warning />}
                                    style={{ marginRight: '10px' }}
                                    variant="contained"
                                    onClick={() => {
                                        setSnackbarState({
                                            ...snackbarState,
                                            message: 'TEST WARNING',
                                            open: true,
                                            type: 'warning',
                                        });
                                    }}
                                >
                                    Warning Message
                                </Button>
                                <Button
                                    size="small"
                                    startIcon={<Info />}
                                    variant="contained"
                                    onClick={() => {
                                        setSnackbarState({
                                            ...snackbarState,
                                            message: 'TEST INFO',
                                            open: true,
                                            type: 'info',
                                        });
                                    }}
                                >
                                    Info Message
                                </Button>
                            </CardContent>
                        </Card>
                    </>
                )}
            </Grid>
            <Snackbar
                anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
                autoHideDuration={1000 + snackbarState.message.length * 60}
                open={snackbarState.open}
                onClose={handleClose}
                key={'bottomcenter'}
            >
                <Alert severity={snackbarState.type}>{snackbarState.message}</Alert>
            </Snackbar>
        </Grid>
    );
};

export default AdvancedView;
