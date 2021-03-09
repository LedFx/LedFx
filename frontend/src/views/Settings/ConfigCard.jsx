import React from 'react';
import { makeStyles } from '@material-ui/core/styles';
import Card from '@material-ui/core/Card';
import CardHeader from '@material-ui/core/CardHeader';
import CardContent from '@material-ui/core/CardContent';
import FormHelperText from '@material-ui/core/FormHelperText';
import InputLabel from '@material-ui/core/InputLabel';
import TextField from '@material-ui/core/TextField';

const useStyles = makeStyles({
    content: {
        display: 'flex',
        flexDirection: 'column',
    },
});

const ConfigCard = ({ settings, error }) => {
    const classes = useStyles();
    return (
        <Card>
            <CardHeader title="Configs" subheader="Manage network and developer settings" />
            <CardContent className={classes.content}>
                <InputLabel id="host-label">Host</InputLabel>
                <TextField disabled label-id="host-label" id="host" value={settings.host} />
                <InputLabel id="port-label">Port</InputLabel>
                <TextField disabled label-id="port-label" id="port" value={settings.port} />
                <InputLabel id="devMode-label">DevMode</InputLabel>
                <TextField
                    disabled
                    label-id="devMode-label"
                    id="devMode"
                    value={settings.devMode}
                />
                {error && <FormHelperText>{error}</FormHelperText>}
            </CardContent>
        </Card>
    );
};

export default ConfigCard;
