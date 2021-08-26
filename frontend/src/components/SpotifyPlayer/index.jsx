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
import PlayArrow from '@material-ui/icons/PlayArrow';
import Pause from '@material-ui/icons/Pause';
import SkipNext from '@material-ui/icons/SkipNext';
import SkipPrevious from '@material-ui/icons/SkipPrevious';
//import CircularProgress from '@material-ui/core/CircularProgress';
import InfoIcon from '@material-ui/icons/Info';
import Link from '@material-ui/core/Link';
import { getScenes, activateScene } from 'modules/scenes';
import Moment from 'react-moment';
import moment from 'moment';
import Slider from "@material-ui/core/Slider"
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

    render() {
        const { playerState, classes,scenes } = this.props;

        return (
            Object.keys(playerState).length == 0 ?
                <Link target="_blank" href="https://support.spotify.com/us/article/spotify-connect/" >
                <Typography color="textPrimary"
                >Using Spotify Connect, select LedFX <InfoIcon></InfoIcon></Typography>
                </Link>
                :
                <AppBar color="default" position='relative' className={classes.appBar}>
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
                                    color="primary"
                                    onChange={(e) => this.handleSelectChange(e)}
                                    labelId='select'>
                                        {scenes.length && scenes.map((s,i) => <option value={s.id} key={i}>{s.name}</option>)}

                                    </Select>
                                </FormControl>
                            </Grid>
                            <Grid item xs={6} justify="center">
                            <div style={{flex: 1, width: '100%'}}> <Slider  aria-labelledby="continuous-slider" value={
                                playerState.position/playerState.duration*100
                                } />
                            <Button style={{marginRight: '1.8rem'}} color="primary" variant="contained"><SkipPrevious /></Button>
                            {playerState.paused === true
                            ?
                            <Button style={{marginRight: '1.8rem'}} color="primary" variant="contained"><PlayArrow /></Button>
                            :
                            <Button style={{marginRight: '1.8rem'}} color="primary" variant="contained"><Pause /></Button> }

                            <Button style={{marginRight: '1.8rem'}} color="primary" variant="contained"><SkipNext /></Button>
                            </div>
                            </Grid>

                            <Grid container item xs={6} justify='center'>

                            <Typography align='center' variant='body1'><div>
                                    Track Position: .
                                    {playerState.paused === false
                                    ?
                                    <Moment
                                    interval={1000}
                                    format="mm:ss"
                                    durationFromNow
                                    >
                                        {moment().add(
                                            playerState.position * -0.001,
                                            's'
                                            )}
                                    </Moment>
                                    : <Moment
                                            interval={0}
                                            format="mm:ss"
                                            durationFromNow
                                            >
                                                {moment().add(playerState.position * -0.001,'s')}
                                                    </Moment>}
                                            </div>
                                    </Typography>
                                    <Typography align='center' variant='body1'><div>
                                    Testing:
                                    {playerState.paused === false
                                    ?
                                    <Moment
                                            interval={1000}
                                            format="ms"
                                            durationFromNow
                                            >
                                                {moment().add(playerState.position * -1,'ms')}
                                                    </Moment>
                                    //moment().add(playerState.position* -0.001, 's')/playerState.duration*100
                                    :
                                    (playerState.position/playerState.duration*100)
                                        } </div>
                                    </Typography>
                                <div>
                                <FormControlLabel
                                    control={<Checkbox color="primary" checked={this.state.includePosition} onChange={(e) => this.handleCheckChange(e)} name="includePosition" />}
                                    label="Include Track Position"
                                /></div>
                                <Button color="primary" variant='contained'>Add Trigger</Button>
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
        accessToken: state.spotify.accessToken,
        scenes: state.scenes.list,
    }),
    { updatePlayerState }
)(withStyles(styles)(SpotifyPlayer));
