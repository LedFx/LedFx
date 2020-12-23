import React, { useEffect, useState } from 'react';
import Grid from '@material-ui/core/Grid';
import { useDispatch, useSelector } from 'react-redux';
import MuiAlert from '@material-ui/lab/Alert';
import Snackbar from '@material-ui/core/Snackbar';

import Typography from '@material-ui/core/Typography';

import Table from '@material-ui/core/Table';
import TableHead from '@material-ui/core/TableHead';
import TableRow from '@material-ui/core/TableRow';
import TableCell from '@material-ui/core/TableCell';
import TableBody from '@material-ui/core/TableBody';

import { getAsyncIntegrations } from 'modules/integrations';
import Card from '../../components/IntegrationComponents/Card';
import CardB from '../../components/IntegrationComponents/CardB';
import Row from '../../components/IntegrationComponents/Row';

function Alert(props) {
    return <MuiAlert elevation={6} variant="filled" {...props} />;
}

const IntegrationsView = () => {
    const intTypes = useSelector(state => state.schemas.integrationTypes || {});
    const instInts = useSelector(state => state.integrations.list || []);
    const dispatch = useDispatch();
    const [snackbarState, setSnackbarState] = useState({ open: false, message: '', type: 'error' });

    const handleClose = () => {
        setSnackbarState({ ...snackbarState, open: false });
    };

    useEffect(() => {
        dispatch(getAsyncIntegrations());
    }, [dispatch]);

    return (
        <Grid container spacing={2}>
            <Grid item xs={12} md={12}>
                <Typography
                    variant="h6"
                    component="h2"
                    color="textPrimary"
                    style={{ marginBottom: '1em' }}
                >
                    Available Integrations
                </Typography>
                <Grid container justify="flex-start" spacing={5}>
                    {intTypes &&
                        intTypes !== {} &&
                        Object.keys(intTypes).map((int, i) => (
                            <Grid key={i} item>
                                <Card intTypes={intTypes} int={int} />
                            </Grid>
                        ))}
                </Grid>
                <Typography
                    variant="h6"
                    component="h2"
                    color="textPrimary"
                    style={{ marginBottom: '1em', marginTop: '3em' }}
                >
                    Installed Integrations
                </Typography>
                <Table>
                    <TableHead>
                        <TableRow>
                            <TableCell>Name</TableCell>
                            <TableCell>Type</TableCell>
                            <TableCell>Settings</TableCell>
                            <TableCell>Actions</TableCell>
                        </TableRow>
                    </TableHead>

                    <TableBody>
                        {instInts &&
                            Object.keys(instInts).map((instInt, i) => (
                                <Row
                                    key={instInts[instInt].id}
                                    installedIntegrations={instInts}
                                    installedIntegration={instInt}
                                />
                            ))}
                    </TableBody>
                </Table>
                <Typography
                    variant="h6"
                    component="h2"
                    color="textPrimary"
                    style={{ marginBottom: '1em', marginTop: '3em' }}
                >
                    Installed Integrations
                </Typography>
                <Grid container justify="flex-start" spacing={5}>
                    {instInts &&
                        Object.keys(instInts).map((instInt, i) => (
                            <Grid key={instInts[instInt].id} item>
                                <CardB int={instInts[instInt]} />
                            </Grid>
                        ))}
                </Grid>
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

export default IntegrationsView;
