import React from 'react';
import Card from '@material-ui/core/Card';
import CardActions from '@material-ui/core/CardActions';
import CardContent from '@material-ui/core/CardContent';
import { makeStyles } from '@material-ui/core/styles';
import Typography from '@material-ui/core/Typography';
import PopoverSure from 'components/VirtualComponents/PopoverSure';
import Button from '@material-ui/core/Button';
import EditIcon from '@material-ui/icons/Edit';
import SettingsIcon from '@material-ui/icons/Settings';
import { deleteAsyncIntegration } from 'modules/integrations';
import { toggleAsyncIntegration } from 'modules/integrations';
import { Switch, Chip } from '@material-ui/core';

const useStyles = makeStyles({
    integrationCard: {
        width: 300,
        height: 170,
        justifyContent: 'space-between',
        display: 'flex',
        flexDirection: 'column',
    },
});

const IntegrationsCard = ({ int }) => {
    const classes = useStyles();

    const handleToggle = props => {
        // console.log('YO', props);
        toggleAsyncIntegration(props);
    };
    return (
        <Card className={classes.integrationCard} variant="outlined">
            <CardContent style={{ paddingBottom: 0 }}>
                <div
                    style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'flex-start',
                        marginBottom: '0.5em',
                    }}
                >
                    <Typography variant="h5" component="h2">
                        {int.config.name}
                    </Typography>
                    <Chip label={`type: ${int.type}`} size="small" />
                </div>
                <Typography style={{ fontSize: '14px' }} color="textSecondary" gutterBottom>
                    {int.config.description}
                </Typography>
                <Typography style={{ fontSize: '14px' }} color="textSecondary" gutterBottom>
                    Status:{' '}
                    {int.status === 3
                        ? 'connecting...'
                        : int.status === 2
                        ? 'disconnecting'
                        : int.status === 1
                        ? 'connected'
                        : int.status === 0
                        ? 'disconnected'
                        : 'Unknown'}
                </Typography>
            </CardContent>
            <CardActions>
                <PopoverSure
                    variant="text"
                    onDeleteVitem={() =>
                        deleteAsyncIntegration({
                            id: int.id,
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
                    <SettingsIcon />
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
                <Switch
                    color="primary"
                    onChange={() =>
                        handleToggle({
                            id: int.id,
                        })
                    }
                    checked={int.active}
                />
            </CardActions>
        </Card>
    );
};

export default IntegrationsCard;
