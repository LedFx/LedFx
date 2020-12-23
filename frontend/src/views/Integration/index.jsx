import React, { useEffect, useState } from 'react';
import Grid from '@material-ui/core/Grid';
import { useDispatch, useSelector } from 'react-redux';
import MuiAlert from '@material-ui/lab/Alert';
import Snackbar from '@material-ui/core/Snackbar';
import Button from '@material-ui/core/Button';

import Card from '@material-ui/core/Card';
import CardActions from '@material-ui/core/CardActions';
import CardContent from '@material-ui/core/CardContent';
import Typography from '@material-ui/core/Typography';
import { makeStyles } from '@material-ui/core/styles';

import Table from '@material-ui/core/Table';
import TableHead from '@material-ui/core/TableHead';
import TableRow from '@material-ui/core/TableRow';
import TableCell from '@material-ui/core/TableCell';
import TableBody from '@material-ui/core/TableBody';

import DialogAddIntegration from 'components/IntegrationComponents/DialogAddIntegration';
import { deleteAsyncIntegration, getAsyncIntegrations } from 'modules/integrations';
import DeleteIcon from '@material-ui/icons/Delete';
import EditIcon from '@material-ui/icons/Edit';
import { Switch } from '@material-ui/core';

import PopoverSure from 'components/VirtualComponents/PopoverSure';
// import * as integrationsProxies from 'proxies/integrations';

function Alert(props) {
    return <MuiAlert elevation={6} variant="filled" {...props} />;
}

const useStyles = makeStyles({
    integrationCard: {
        width: 220,
        height: 220,
        justifyContent: 'space-between',
        display: 'flex',
        flexDirection: 'column',
    },
    bullet: {
        display: 'inline-block',
        margin: '0 2px',
        transform: 'scale(0.8)',
    },
    title: {
        fontSize: 14,
    },
    pos: {
        marginBottom: 12,
    },
});

const IntegrationsView = () => {
    const integrationTypes = useSelector(state => state.schemas.integrationTypes || {});
    const installedIntegrations = useSelector(state => state.integrations.list || []);
    const classes = useStyles();

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
                    {integrationTypes &&
                        integrationTypes !== {} &&
                        Object.keys(integrationTypes).map((integration, i) => (
                            <Grid key={i} item>
                                <Card className={classes.integrationCard} variant="outlined">
                                    <CardContent>
                                        <Typography
                                            className={classes.title}
                                            color="textSecondary"
                                            gutterBottom
                                        >
                                            Integration
                                        </Typography>
                                        <Typography variant="h5" component="h2">
                                            {integrationTypes[integration].name}
                                        </Typography>
                                        <Typography className={classes.pos} color="textSecondary">
                                            v0.0.1
                                        </Typography>
                                        <Typography variant="body2" component="p">
                                            {integrationTypes[integration].description}
                                        </Typography>
                                    </CardContent>
                                    <CardActions>
                                        <DialogAddIntegration
                                            integration={integrationTypes[integration].id}
                                        />
                                    </CardActions>
                                </Card>
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
                <Table className={classes.table}>
                    <TableHead>
                        <TableRow>
                            <TableCell>Name</TableCell>
                            <TableCell>Type</TableCell>
                            <TableCell>Settings</TableCell>
                            <TableCell>Actions</TableCell>
                        </TableRow>
                    </TableHead>

                    <TableBody>
                        {installedIntegrations &&
                            Object.keys(installedIntegrations).map((installedIntegration, i) => (
                                <TableRow key={installedIntegrations[installedIntegration].id}>
                                    <TableCell>
                                        {installedIntegrations[installedIntegration].config.name}
                                    </TableCell>
                                    <TableCell>
                                        {installedIntegrations[installedIntegration].type}
                                    </TableCell>
                                    <TableCell>
                                        {JSON.stringify(
                                            installedIntegrations[installedIntegration]
                                        )}
                                    </TableCell>
                                    <TableCell>
                                        <div style={{ display: 'flex' }}>
                                            <Switch color="primary" />
                                            <PopoverSure
                                                onDeleteVitem={() =>
                                                    deleteAsyncIntegration({
                                                        id:
                                                            installedIntegrations[
                                                                installedIntegration
                                                            ].id,
                                                    })
                                                }
                                            />
                                            <Button
                                                variant="text"
                                                color="secondary"
                                                onClick={() => {
                                                    console.log('deleting');
                                                }}
                                            >
                                                <DeleteIcon />
                                            </Button>
                                            <Button
                                                variant="text"
                                                color="secondary"
                                                onClick={() => {
                                                    console.log('edit');
                                                }}
                                            >
                                                <EditIcon />
                                            </Button>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ))}
                    </TableBody>
                </Table>
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
