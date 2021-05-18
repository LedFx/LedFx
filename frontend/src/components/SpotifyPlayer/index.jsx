import React, { useEffect } from 'react';
import { connect, useSelector, useDispatch } from 'react-redux';
import withStyles from '@material-ui/core/styles/withStyles';
import { makeStyles } from '@material-ui/core/styles';
import Button from '@material-ui/core/Button';
//import Card from '@material-ui/core/Card';
//import CardHeader from '@material-ui/core/CardHeader';
//import CardContent from '@material-ui/core/CardContent';
import { AppBar, Checkbox, FormControl, FormControlLabel, Grid, InputLabel, Select, Typography } from '@material-ui/core';
import { updatePlayerState  } from 'modules/spotify'
//import AddCircleIcon from '@material-ui/icons/AddCircle';
//import PlayArrowIcon from '@material-ui/icons/PlayArrow';
//import CircularProgress from '@material-ui/core/CircularProgress';
import InfoIcon from '@material-ui/icons/Info';
import Link from '@material-ui/core/Link';
import { getScenes, activateScene } from 'modules/scenes';
import Moment from 'react-moment';
import moment from 'moment';
//import uniqBy from 'lodash/uniqBy';

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

const useStyles = makeStyles(theme => ({
    sceneButton: {
        size: 'large',
        margin: theme.spacing(1),
    },
    submitControls: {
        display: 'flex',
        flexWrap: 'wrap',
        width: '100%',
        height: '100%',
    },
}));

//function getScenes();

function msToTime(duration) {
    var milliseconds = parseInt((duration % 1000) / 100),
      seconds = Math.floor((duration / 1000) % 60),
      minutes = Math.floor((duration / (1000 * 60)) % 60),
      hours = Math.floor((duration / (1000 * 60 * 60)) % 24);
  
    hours = (hours < 10) ? "0" + hours : hours;
    minutes = (minutes < 10) ? "0" + minutes : minutes;
    seconds = (seconds < 10) ? "0" + seconds : seconds;
  
    return minutes + ":" + seconds + "." + milliseconds;
  }
  //console.log(msToTime(300000))


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
        if (Object.keys(this.props.playerState).length === 0 && this.props.playerState.constructor == Object) {
            console.log('creating player')
            this.createWebPlayer(this.props.accessToken)
        }
    }

    componentDidUpdate(prevProps, prevState) {
        if (this.props.playerState.position !== prevProps.playerState.position) {
            this.setState({sliderPositon: this.props.playerState.position})
        }
    }

     //componentGetScenes(() => {  
       //dispatch(getScenes()}
       //));

    render() {
        const { playerState, classes } = this.props;
        return (
            Object.keys(playerState).length == 0 ?
                <Link target="_blank" href="https://support.spotify.com/us/article/spotify-connect/" >
                <Typography color="textPrimary"
                >Using Spotify Connect, select LedFX <InfoIcon></InfoIcon></Typography>
                </Link>
                :
                <AppBar position='relative' className={classes.appBar}>
                    <Grid container justify='space-around' alignItems='center' className={classes.container}>
                        <Grid container item xs={4}>
                        <img style={{alignItems: 'center'}} className={classes.albumImg} src={playerState.track_window.current_track.album.images[0].url} alt=""/>  
                            <div style={{width: '200px', marginLeft: '2vw', display: 'flex', alignItems: 'center'}}>
                                <Typography align='center' variant='body1'>
                                    Song: {playerState.track_window.current_track.name} 
                                    <div>Artist: {playerState.track_window.current_track.artists[0].name}</div>
                                </Typography>
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
                            <Typography align='center' variant='body1'><div>
                                    Track Position: 
                                    {playerState.paused = true
                                    ?
                                    <Moment
                                    interval={0}
                                    format="hh:mm:ss"
                                    durationFromNow
                                    >
                                        {moment().add(
                                            playerState.position * -0.001,
                                            's'
                                            )}
                                    </Moment>
                                    : <Moment
                                            interval={1000}
                                            format="hh:mm:ss"
                                            durationFromNow
                                            >
                                                {moment().add(
                                                    playerState.position * -0.001,
                                                    's'
                                                    )}
                                                    </Moment>}
                                            </div>
                                    </Typography>
                                <div>
                                <FormControlLabel
                                    control={<Checkbox checked={this.state.includePosition} onChange={(e) => this.handleCheckChange(e)} name="includePosition" />}
                                    label="Include Track Position"
                                /></div>
                                <Button variant='contained'>Add Trigger</Button>
                            </Grid>
                        </Grid>
                    </Grid>
                </AppBar>
        );
    }
}

/*
SongControls.propTypes = {
    timeElapsed: PropTypes.number,
    songPlaying: PropTypes.bool,
    songPaused: PropTypes.bool,
    songName: PropTypes.string,
    artistName: PropTypes.string,
    stopSong: PropTypes.func,
    resumeSong: PropTypes.func,
    increaseSongTime: PropTypes.func,
    pauseSong: PropTypes.func,
    songs: PropTypes.array,
    songDetails: PropTypes.object,
    audioControl: PropTypes.func
  };
  */

export default connect(
    state => ({
        playerState: state.spotify.playerState,
        accessToken: state.spotify.accessToken
    }),
    { updatePlayerState }
)(withStyles(styles)(SpotifyPlayer));
