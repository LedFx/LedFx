import React from 'react';
import { makeStyles } from '@material-ui/core/styles';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import FormHelperText from '@material-ui/core/FormHelperText';
import Typography from '@material-ui/core/Typography';
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
            <CardContent className={classes.content}>
                <Typography variant="h6" color="textSecondary" gutterBottom>
                    Configs
                </Typography>
                <InputLabel id="host-label">Host</InputLabel>
                <TextField disabled labelId="host-label" id="host" value={settings.host} />
                <InputLabel id="port-label">Port</InputLabel>
                <TextField disabled labelId="port-label" id="port" value={settings.port} />
                <InputLabel id="devMode-label">DevMode</InputLabel>
                <TextField disabled labelId="devMode-label" id="devMode" value={settings.devMode} />
                {error && <FormHelperText>{error}</FormHelperText>}
            </CardContent>
        </Card>
    );
};

export default ConfigCard;
