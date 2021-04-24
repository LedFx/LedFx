import React, {useEffect} from 'react';
import {connect, useDispatch} from 'react-redux';
import Card from '@material-ui/core/Card';
import CardActions from '@material-ui/core/CardActions';
import CardContent from '@material-ui/core/CardContent';
import { makeStyles } from '@material-ui/core/styles';
import { Grid, Typography } from '@material-ui/core';
import Link from '@material-ui/core/Link';
import PopoverSure from 'components/VirtualComponents/PopoverSure';
import Button from '@material-ui/core/Button';
import EditIcon from '@material-ui/icons/Edit';
import { deleteAsyncIntegration } from 'modules/integrations';
import { toggleAsyncIntegration } from 'modules/integrations';
import { Switch, Chip } from '@material-ui/core';
import DialogAddEventListener from 'components/IntegrationComponents/DialogAddEventListener';
import { getAsyncqlclisteners  } from 'modules/qlc'
//import { Call } from '@material-ui/icons';


const useStyles = makeStyles({
    integrationCard: {
        width: 300,
        height: 280,
        justifyContent: 'space-between',
        display: 'flex',
        flexDirection: 'column',
    },
});

const IntegrationsCard = ({ int }) => {
    const classes = useStyles();
    const dispatch = useDispatch();
    const handleToggle = (props) => toggleAsyncIntegration(props);
    const preventDefault = (event) => event.preventDefault();

    useEffect(() => {     
        // EVERTHING HERE IS ONLY CALLED ONCE WHEN THIS COMPONENT IS RENDERED   
       dispatch(getAsyncqlclisteners(int.id))
    }, [dispatch, int.id])
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
                <Typography color="textSecondary" gutterBottom>
                <Link target="_blank" href="http://127.0.0.1:9999" >   
                    {int.type === 'qlc'
                    ? `QLC+ API: http://${int.config.ip_address}:${int.config.port}`
                    : ''}
                    </Link>
                </Typography>
                <Typography style={{ fontSize: '14px' }} color="textSecondary" gutterBottom>
                    Description: {int.config.description}
                </Typography>
            </CardContent>
            <CardActions>
                {int.status === 1 & int.type === 'qlc'
                ? <DialogAddEventListener integration={int} />
                : int.status !== 1 & int.type === 'qlc'
                ? 'Must be in connected status, to add new event listener. Guide: shorturl.at/uMSV7'
                : ''}
                
                {int.type === 'spotify' && int.active !== 'true' /* && !spotify.accessToken && !spotify.refreshToken */
                ? 
                // For Connect to Spotify button
                <Button variant='contained' color="primary" onClick={() => this.beginAuth()}> 
                    <Typography>Connect to Spotify</Typography>
                </Button> 
                    : ''}
            </CardActions>
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
                    //Need to do, onClick edit Integration.
                >
                    <EditIcon />
                </Button>
                <Switch
                    //checked={false}
                    color="primary"
                    onChange={() => handleToggle(int.id)}
                    checked={int.active}
                    //onClick={handleClickListItem}
                    //Need to do, onClick: Re-render switch and integrations Redux.
                />
                
            </CardActions>
        </Card>
        
    );
};



/*export default connect(
    state => ({
        spotify: state.spotify
    }),
    { checkCookiesForTokens, finishAuth, refreshAuth }
)(withStyles(styles)(SpotifyView));*/

export default IntegrationsCard;

                            