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
            <CardHeader title="Info" subheader="View detailed informations" />
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
                    defaultValue={settings.devMode}
                />
                <InputLabel id="backend-version-label">LedFx-Version</InputLabel>
                <TextField disabled label-id="backend-version-label" id="backend-version" defaultValue={settings.version} />
                <InputLabel id="frontend-version-label">Frontend-Version</InputLabel>
                <TextField disabled label-id="frontend-version-label" id="frontend-version" value={process.env.REACT_APP_VERSION} />
                <InputLabel id="commit-label">BuildCommit</InputLabel>
                <TextField disabled label-id="commit-label" id="commit" value={settings.git_build_commit} />
                {error && <FormHelperText>{error}</FormHelperText>}
            </CardContent>
        </Card>
    );
};

export default ConfigCard;
