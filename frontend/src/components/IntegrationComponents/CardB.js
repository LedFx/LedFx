import React from 'react';
import Card from '@material-ui/core/Card';
import CardActions from '@material-ui/core/CardActions';
import CardContent from '@material-ui/core/CardContent';
import { makeStyles } from '@material-ui/core/styles';
import Typography from '@material-ui/core/Typography';
import PopoverSure from 'components/VirtualComponents/PopoverSure';
import Button from '@material-ui/core/Button';
import EditIcon from '@material-ui/icons/Edit';
import { deleteAsyncIntegration } from 'modules/integrations';
import { toggleAsyncIntegration } from 'modules/integrations';
import { Switch, Chip } from '@material-ui/core';
import AddCircleIcon from '@material-ui/icons/AddCircle';
// import DialogAddIntegration from 'components/IntegrationComponents/DialogAddIntegration';

const useStyles = makeStyles({
    integrationCard: {
        width: 300,
        height: 230,
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
                <Typography variant="h6" component="p" gutterBottom>
                    Status:{' '}
                    {int.status === 3
                        ? 'Connecting...'
                        : int.status === 2
                        ? 'Disconnecting'
                        : int.status === 1
                        ? 'Connected'
                        : int.status === 0
                        ? 'Disconnected'
                        : 'Unknown'}
                </Typography>
                <Typography style={{ fontSize: '14px' }} color="textSecondary" gutterBottom>
                    QLC+ IP Address: {int.config.ip_address}:{int.config.port}
                </Typography>
                <Typography style={{ fontSize: '14px' }} color="textSecondary" gutterBottom>
                    Description: {int.config.description}
                </Typography>
                <Button
                    variant="contained"
                    color="primary"
                    aria-label="Add"
                    className={classes.button}
                    endIcon={<AddCircleIcon />}
                    aria-haspopup="true"
                    //onClick={handleClickListItem}
                    role="listitem"
                >
                    ADD Event Listener
                </Button>
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
