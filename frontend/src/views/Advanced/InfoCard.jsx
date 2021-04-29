import React from 'react';
import { useSelector } from "react-redux"
import { makeStyles } from '@material-ui/core/styles';
import Card from '@material-ui/core/Card';
import CardHeader from '@material-ui/core/CardHeader';
import CardContent from '@material-ui/core/CardContent';
import TextField from '@material-ui/core/TextField';

const useStyles = makeStyles({
    content: {
        display: 'flex',
        flexDirection: 'column',
    },
});

const InfoCard = () => {
    const classes = useStyles();
    const settings = useSelector(state => state.settings)
    const version = useSelector(state => state.settings.version);
    return <Card>
        <CardHeader title="Info" subheader="View detailed informations" />
        <CardContent className={classes.content}>
            <TextField disabled label="Host" id="host" value={settings.host} />
            <TextField disabled label="Port" id="port" value={settings.port} />
            <TextField
                disabled
                label="DevMode"
                id="devMode"
                defaultValue={settings.devMode}
            />

            <TextField disabled label="LedFx-Version" id="backend-version" defaultValue={version} />
            <TextField disabled label="Frontend-Version-label" id="frontend-version" value={process.env.REACT_APP_VERSION} />
            <TextField disabled label="Built-commit" id="commit" value={settings.git_build_commit} />


        </CardContent>
    </Card>
};

export default InfoCard;
