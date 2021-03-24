import React from 'react';
import { connect } from 'react-redux';
import withStyles from '@material-ui/core/styles/withStyles';
import Button from '@material-ui/core/Button';
import { AppBar, Checkbox, FormControl, FormControlLabel, Grid, InputLabel, Select, Typography } from '@material-ui/core';
import { updatePlayerState  } from 'modules/spotify'
import PlayArrowIcon from '@material-ui/icons/PlayArrow';

const styles = theme => ({
    appBar: {
       // top: 'auto',
       // bottom: 0,
       height: '15vh'
    },
    paper: {
        height: '100%',
        display: "flex",
        flexDirection: "column",
        justifyContent: "center"
    },
    wrapper: {
        width: '100%'
    },
    container: {
        height: '100%'
    },
    albumImg: {
        maxWidth: '100px',
        maxHeight: '100%'
    }
});


class SpotifyPlayer extends React.Component {
    constructor(props) {
        super(props);
        this.state = { 
            sliderPositon: 0,
            includePosition: 'false',
            effects: ''
        }
    };

    createWebPlayer(token) {
        window.onSpotifyWebPlaybackSDKReady = () => {
            const player = new window.Spotify.Player({
                name: 'LedFX',
                getOAuthToken: cb => { cb(token); }
            });
            player.addListener('initialization_error', ({ message }) => { console.error(message); });
            player.addListener('authentication_error', ({ message }) => { console.error(message); });
            player.addListener('account_error', ({ message }) => { console.error(message); });
            player.addListener('playback_error', ({ message }) => { console.error(message); });
            player.addListener('player_state_changed', state => { 
                if (state.position < 5 || state.position > 500) {
                    this.props.updatePlayerState(state); 
                }
            });
            player.addListener('ready', ({ device_id }) => {
                console.log('Ready with Device ID', device_id);
            });
            player.addListener('not_ready', ({ device_id }) => {
                console.log('Device ID has gone offline', device_id);
            });
            player.connect();
        };
        let script = window.document.createElement('script')
        script.setAttribute('src', 'https://sdk.scdn.co/spotify-player.js')
        window.document.head.appendChild(script);
    }

    handleSliderChange(e,v) {
        console.log(v)
        this.setState({sliderPositon: v})
    }

    handleCheckChange = (event) => {
        this.setState({ ...this.state, [event.target.name]: event.target.checked });
    };

    handleSelectChange = (event) => {
        this.setState({ ...this.state, effects: event.target.value });
    };

    componentDidMount() {
        if (Object.keys(this.props.playerState).length == 0 && this.props.playerState.constructor == Object) {
            console.log('creating player')
            this.createWebPlayer(this.props.accessToken)
        }
    }

    componentDidUpdate(prevProps, prevState) {
        if (this.props.playerState.position !== prevProps.playerState.position) {
            this.setState({sliderPositon: this.props.playerState.position})
        }
    }

    render() {
        const { playerState, classes } = this.props;
        return (
            Object.keys(playerState).length == 0 ?
                <Typography>Select LedFX using Spotify Connect</Typography>
                :
                <AppBar position='relative' className={classes.appBar}>
                    <Grid container justify='space-around' alignItems='center' className={classes.container}>
                        <Grid container item xs={4}>
                        <img className={classes.albumImg} src={playerState.track_window.current_track.album.images[0].url} alt=""/>  
                            <div style={{width: '200px', marginLeft: '2vw', display: 'flex', alignItems: 'center'}}>
                                <Typography align='center' variant='body1'>{playerState.track_window.current_track.name}</Typography> 
                            </div>
                            
                        </Grid>
                        <Grid item container xs={7}>
                            <Grid item xs={6}>
                                <FormControl className={classes.formControl}>
                                  <InputLabel id='select'>Scenes</InputLabel>
                                  <Select
                                    value={this.state.effects}
                                    onChange={(e) => this.handleSelectChange(e)}
                                    labelId='select'>
                                        <option value={10}>Ten</option>
                                        <option value={20}>Twenty</option>
                                        <option value={30}>Thirty</option>
                                    </Select>
                                </FormControl>
                            </Grid>
                            <Grid container item xs={6} justify='center'>
                                <FormControlLabel
                                    control={<Checkbox checked={this.state.includePosition} onChange={(e) => this.handleCheckChange(e)} name="includePosition" />}
                                    label="Include Track Position"
                                />
                                <Button variant='contained'>Add Trigger</Button>
                            </Grid>
                        </Grid>
                    </Grid>
                </AppBar>
        );
    }
}

export default connect(
    state => ({
        playerState: state.spotify.playerState,
        accessToken: state.spotify.accessToken
    }),
    { updatePlayerState }
)(withStyles(styles)(SpotifyPlayer));
