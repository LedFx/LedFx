import React from 'react';
import { ToastContainer, toast } from 'react-toastify';
import { connect } from 'react-redux';
import withStyles from '@material-ui/core/styles/withStyles';
import Button from '@material-ui/core/Button';
import {
    AppBar,
    Checkbox,
    FormControl,
    FormControlLabel,
    Grid,
    InputLabel,
    Select,
    Typography,
    Link,
    Slider,
    Accordion,
    AccordionSummary,
    AccordionDetails,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Paper,
} from '@material-ui/core';
import { PlayArrow, Pause, SkipNext, SkipPrevious } from '@material-ui/icons';
import InfoIcon from '@material-ui/icons/Info';
import ExpandMoreIcon from '@material-ui/icons/ExpandMore';
import Moment from 'react-moment';
import moment from 'moment';
import { updatePlayerState } from 'modules/spotify';
import { getAsyncIntegrations } from 'modules/integrations';
import { activateScene } from 'modules/scenes';
import { addTrigger } from 'proxies/spotify';
import RadarChart from 'components/SpotifyPlayer/RadarChart';
import Layout from 'components/AudioAnalysis/Layout';

const data = {
    datasets: [
        {
            label: 'First Dataset',
            data: [65, 59, 90, 81, 56, 55, 40],
            fill: true,
            backgroundColor: 'rgba(255, 99, 132, 0.2)',
            borderColor: 'rgb(255, 99, 132)',
            pointBackgroundColor: 'rgb(255, 99, 132)',
            pointBorderColor: '#fff',
            pointHoverBackgroundColor: '#fff',
            pointHoverBorderColor: 'rgb(255, 99, 132)',
        },
        {
            label: 'Second Dataset',
            data: [28, 48, 40, 19, 96, 27, 100],
            fill: true,
            backgroundColor: 'rgba(54, 162, 235, 0.2)',
            borderColor: 'rgb(54, 162, 235)',
            pointBackgroundColor: 'rgb(54, 162, 235)',
            pointBorderColor: '#fff',
            pointHoverBackgroundColor: '#fff',
            pointHoverBorderColor: 'rgb(54, 162, 235)',
        },
    ],
};

const styles = theme => ({
    appBar: {
        // top: 'auto',
        // bottom: 0,
        height: '15vh',
    },
    paper: {
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
    },
    wrapper: {
        width: '100%',
    },
    container: {
        height: '100%',
    },
    albumImg: {
        maxWidth: '100px',
        maxHeight: '100%',
    },
});

class SpotifyPlayer extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            sliderPositon: 0,
            includePosition: 'false',
            effects: '',
            play: false,
            player: {},
            expanded: true,
            pitches: {
                C: true,
                'C#': true,
                D: true,
                'D#': true,
                E: true,
                F: true,
                'F#': true,
                G: true,
                'G#': true,
                A: true,
                'A#': true,
                B: true,
            },
        };
    }

    createWebPlayer(token) {
        window.onSpotifyWebPlaybackSDKReady = () => {
            const player = new window.Spotify.Player({
                name: 'LedFX',
                getOAuthToken: cb => {
                    cb(token);
                },
            });

            player.addListener('initialization_error', ({ message }) => {
                console.error(message);
            });
            player.addListener('authentication_error', ({ message }) => {
                console.error(message);
            });
            player.addListener('account_error', ({ message }) => {
                console.error(message);
            });
            player.addListener('playback_error', ({ message }) => {
                console.error(message);
            });
            player.addListener('player_state_changed', state => {
                console.log(state);
                if (state !== null) {
                    if (state.position < 5 || state.position > 500) {
                        this.props.updatePlayerState(state);
                    }
                } else {
                    this.props.updatePlayerState({});
                }
            });
            player.addListener('ready', ({ device_id }) => {
                console.log('Ready with Device ID', device_id);
            });
            player.addListener('not_ready', ({ device_id }) => {
                console.log('Device ID has gone offline', device_id);
            });
            this.setState({ player: player });
            this.state.player.connect();
        };
        let script = window.document.createElement('script');
        script.setAttribute('src', 'https://sdk.scdn.co/spotify-player.js');
        window.document.head.appendChild(script);
    }

    handleSliderChange(e, v) {
        let percentage = v / 100;
        let progress = this.props.playerState.duration * percentage;
        this.state.player.seek(progress);
    }

    handleCheckChange = event => {
        this.setState({ ...this.state, [event.target.name]: event.target.checked });
    };

    handleSelectChange = event => {
        this.setState({ ...this.state, effects: event.target.value });
    };

    handleAddTrigger = async event => {
        let exist = false;
        let temp = this.props.integrations ? this.props.integrations.data : {};
        let currentTime = parseInt(this.props.playerState.position / 1000);
        let currentSongName = this.props.playerState.track_window.current_track.name;
        Object.keys(temp).map(function (key, index) {
            let temp1 = temp[key];

            Object.keys(temp1).map(function (key, index) {
                if (temp1[key].constructor === Array) {
                    if (currentTime === temp1[key][2] && currentSongName === temp1[key][1]) {
                        exist = true;
                    }
                }
                return true;
            });
            return true;
        });
        if (!exist) {
            if (this.state.effects !== '') {
                let trigger = {
                    scene_id: this.state.effects,
                    song_id: this.props.playerState.track_window.current_track.id,
                    song_name: this.props.playerState.track_window.current_track.name,
                    song_position: this.state.includePosition
                        ? Math.round(this.props.playerState.position / 1000)
                        : 0,
                };
                if (await addTrigger(trigger)) {
                    toast.success('Trigger added');
                    this.props.getAsyncIntegrations();
                } else {
                    toast.error('Failed to add trigger');
                }
            } else {
                toast.error('Please select a trigger');
            }
        } else {
            toast.error('Cannot add trigger to same position for one song');
        }
    };

    getTime(duration) {
        var seconds = Math.floor((duration / 1000) % 60),
            minutes = Math.floor((duration / (1000 * 60)) % 60);
        minutes = minutes < 10 ? '0' + minutes : minutes;
        seconds = seconds < 10 ? '0' + seconds : seconds;

        return minutes + ':' + seconds;
    }

    activateSceneHandler = sceneName => {
        this.props.activateScene(sceneName);
    };

    componentDidMount() {
        if (
            Object.keys(this.props.playerState).length === 0 &&
            this.props.playerState.constructor === Object
        ) {
            console.log('creating player');
            this.createWebPlayer(this.props.accessToken);
            console.log(this.props.integrations);
        }
    }

    componentDidUpdate(prevProps, prevState) {
        if (this.props.playerState.position !== prevProps.playerState.position) {
            this.setState({
                sliderPositon:
                    (this.props.playerState.position / this.props.playerState.duration) * 100,
            });
            this.state.player.getCurrentState().then(state => {
                if (
                    parseInt(prevProps.playerState.position / 1000) !==
                        parseInt(this.props.playerState.position / 1000) &&
                    state != null
                ) {
                    let temp = this.props.integrations ? this.props.integrations.data : {};
                    let currentTime = parseInt(this.props.playerState.position / 1000);
                    let currentSongName = this.props.playerState.track_window.current_track.name;
                    let activateSceneHandlerTemp = this.activateSceneHandler;
                    Object.keys(temp).map(function (key, index) {
                        let temp1 = temp[key];
                        let sceneName = temp1.name;
                        // let sceneId = temp1.name;
                        Object.keys(temp1).map(function (key, index) {
                            if (temp1[key].constructor === Array) {
                                if (
                                    currentTime === temp1[key][2] &&
                                    currentSongName === temp1[key][1]
                                ) {
                                    activateSceneHandlerTemp(sceneName);
                                    console.log('Matched');
                                }
                            }
                            return true;
                        });
                        return true;
                    });
                    console.log(currentTime);
                }
                this.props.updatePlayerState(state, this.props.audioFeatures);

                if (state == null) {
                    this.props.updatePlayerState({});
                }
            });
        }
    }

    render() {
        const { playerState, classes, scenes, audioFeatures } = this.props;

        const rows = [];
        function capitalizeFirstLetter(string) {
            return string.charAt(0).toUpperCase() + string.slice(1);
        }

        if (audioFeatures) {
            Object.keys(audioFeatures).map(function (key, index) {
                if (Number(audioFeatures[key]))
                    rows.push({
                        name: capitalizeFirstLetter(key.replace('_', ' ')),
                        value: audioFeatures[key],
                    });
                return true;
            });
        }

        return Object.keys(playerState).length === 0 ? (
            <Link target="_blank" href="https://support.spotify.com/us/article/spotify-connect/">
                <Typography color="textPrimary">
                    Using Spotify Connect, select LedFX <InfoIcon></InfoIcon>
                </Typography>
            </Link>
        ) : (
            <AppBar
                color="default"
                position="relative"
                className={classes.appBar}
                style={{ height: 'auto', paddingBottom: '10px' }}
            >
                <Grid
                    container
                    justify="space-around"
                    alignItems="center"
                    className={classes.container}
                >
                    <Grid container item xs={12} sm={12} md={12} lg={4}>
                        <img
                            style={{ alignItems: 'center' }}
                            className={classes.albumImg}
                            src={playerState.track_window.current_track.album.images[0].url}
                            alt=""
                        />
                        <div
                            style={{
                                width: '260px',
                                marginLeft: '2vw',
                                display: 'flex',
                                alignItems: 'center',
                            }}
                        >
                            <Typography align="center" variant="body1">
                                <div style={{ fontWeight: 'bold' }}>
                                    {playerState.track_window.current_track.name}
                                </div>
                                <div style={{ fontSize: '14px', color: '#4c4c4c' }}>
                                    {playerState.track_window.current_track.artists.length > 1
                                        ? playerState.track_window.current_track.artists.map(
                                              (artist, index) => {
                                                  if (index === 0) return artist.name + ', ';
                                                  else if (index === 1) {
                                                      return artist.name;
                                                  } else {
                                                      return ', ' + artist.name;
                                                  }
                                              }
                                          )
                                        : playerState.track_window.current_track.artists[0].name}
                                </div>
                            </Typography>
                        </div>
                    </Grid>
                    <Grid
                        item
                        xs={10}
                        sm={10}
                        md={10}
                        lg={4}
                        justify="center"
                        style={{ paddingTop: '10px' }}
                    >
                        <div style={{ flex: 1, width: '100%' }}>
                            <div
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'space-between',
                                }}
                            >
                                {playerState.paused === false ? (
                                    <Moment interval={1000} format="mm:ss" durationFromNow>
                                        {moment().add(playerState.position * -0.001, 's')}
                                    </Moment>
                                ) : (
                                    this.getTime(playerState.position)
                                )}

                                <Slider
                                    style={{ width: '70%' }}
                                    aria-labelledby="continuous-slider"
                                    value={this.state.sliderPositon}
                                    onChange={this.handleSliderChange.bind(this)}
                                    min={1}
                                    max={100}
                                />
                                {this.getTime(playerState.duration)}
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-evenly' }}>
                                <Button
                                    style={{ marginRight: '1.8rem' }}
                                    color="primary"
                                    variant="contained"
                                    onClick={() => {
                                        this.state.player.previousTrack();
                                    }}
                                >
                                    <SkipPrevious />
                                </Button>
                                {playerState.paused === true ? (
                                    <Button
                                        style={{ marginRight: '1.8rem' }}
                                        color="primary"
                                        variant="contained"
                                        onClick={() => {
                                            this.state.player.togglePlay();
                                        }}
                                    >
                                        <PlayArrow />
                                    </Button>
                                ) : (
                                    <Button
                                        style={{ marginRight: '1.8rem' }}
                                        color="primary"
                                        variant="contained"
                                        onClick={() => {
                                            this.state.player.togglePlay();
                                        }}
                                    >
                                        <Pause />
                                    </Button>
                                )}
                                <Button
                                    style={{ marginRight: '1.8rem' }}
                                    color="primary"
                                    variant="contained"
                                    onClick={() => {
                                        this.state.player.nextTrack();
                                    }}
                                >
                                    <SkipNext />
                                </Button>
                            </div>
                        </div>
                    </Grid>
                    <Grid item container xs={12} sm={12} md={12} lg={4} justify="center">
                        <Grid item xs={6} justify="center" align="center">
                            <FormControl className={classes.formControl}>
                                <InputLabel id="select">Scenes</InputLabel>
                                <Select
                                    value={this.state.effects}
                                    color="primary"
                                    onChange={e => this.handleSelectChange(e)}
                                    labelId="select"
                                >
                                    {scenes.length &&
                                        scenes.map((s, i) => (
                                            <option value={s.id} key={i}>
                                                {s.name}
                                            </option>
                                        ))}
                                </Select>
                            </FormControl>
                        </Grid>
                        <Grid container item xs={12} justify="center" align="center">
                            <div style={{ display: 'flex', alignItems: 'center' }}>
                                <FormControlLabel
                                    control={
                                        <Checkbox
                                            color="primary"
                                            checked={this.state.includePosition}
                                            onChange={e => this.handleCheckChange(e)}
                                            name="includePosition"
                                        />
                                    }
                                    label="Include Track Position"
                                />
                                {playerState.paused === false ? (
                                    <Moment
                                        interval={1000}
                                        format="mm:ss"
                                        durationFromNow
                                        style={{ fontSize: '15px' }}
                                    >
                                        {moment().add(playerState.position * -0.001, 's')}
                                    </Moment>
                                ) : (
                                    <Moment
                                        interval={0}
                                        format="mm:ss"
                                        durationFromNow
                                        style={{ fontSize: '15px' }}
                                    >
                                        {moment().add(playerState.position * -0.001, 's')}
                                    </Moment>
                                )}
                            </div>
                            <Grid container item xs={12} justify="center">
                                <Button
                                    color="primary"
                                    variant="contained"
                                    onClick={e => this.handleAddTrigger(e)}
                                >
                                    Add Trigger
                                </Button>
                            </Grid>
                        </Grid>
                    </Grid>
                    <Accordion
                        style={{ width: '100%' }}
                        expanded={this.state.expanded}
                        onChange={() => this.setState({ expanded: !this.state.expanded })}
                    >
                        <AccordionSummary
                            expandIcon={<ExpandMoreIcon />}
                            aria-controls="panel1a-content"
                            id="panel1a-header"
                            style={{ width: '100%' }}
                        >
                            <Typography>Audio Features</Typography>
                        </AccordionSummary>
                        <AccordionDetails>
                            <Grid md={12} container item style={{ margin: '0px 20px' }}>
                                <Grid xs={6} item>
                                    <TableContainer component={Paper}>
                                        <Table sx={{ minWidth: 650 }} aria-label="simple table">
                                            <TableHead>
                                                <TableRow>
                                                    <TableCell style={{ fontWeight: '700' }}>
                                                        Name
                                                    </TableCell>
                                                    <TableCell
                                                        style={{ fontWeight: '700' }}
                                                        align="right"
                                                    >
                                                        Value
                                                    </TableCell>
                                                </TableRow>
                                            </TableHead>
                                            <TableBody>
                                                <TableRow
                                                    key={'tempo'}
                                                    style={{ cursor: 'pointer' }}
                                                >
                                                    <TableCell component="th" scope="row">
                                                        BPM (Tempo)
                                                    </TableCell>
                                                    <TableCell align="right">
                                                        {audioFeatures.tempo}
                                                    </TableCell>
                                                </TableRow>
                                                <TableRow key={'key'} style={{ cursor: 'pointer' }}>
                                                    <TableCell component="th" scope="row">
                                                        Pitch class (Key)
                                                    </TableCell>
                                                    <TableCell align="right">
                                                        {audioFeatures.key
                                                            ? audioFeatures.key === 0
                                                                ? 'C'
                                                                : audioFeatures.key === 1
                                                                ? 'C#'
                                                                : audioFeatures.key === 2
                                                                ? 'D'
                                                                : audioFeatures.key === 3
                                                                ? 'D#'
                                                                : audioFeatures.key === 4
                                                                ? 'E'
                                                                : audioFeatures.key === 5
                                                                ? 'F'
                                                                : audioFeatures.key === 6
                                                                ? 'F#'
                                                                : audioFeatures.key === 7
                                                                ? 'G'
                                                                : audioFeatures.key === 8
                                                                ? 'G#'
                                                                : audioFeatures.key === 9
                                                                ? 'A'
                                                                : audioFeatures.key === 10
                                                                ? 'A#'
                                                                : audioFeatures.key === 11
                                                                ? 'B'
                                                                : 'N/A'
                                                            : 'N/A'}
                                                    </TableCell>
                                                </TableRow>
                                                <TableRow
                                                    key={'mode'}
                                                    style={{ cursor: 'pointer' }}
                                                >
                                                    <TableCell component="th" scope="row">
                                                        Modality/Mode (Major/Minor)
                                                    </TableCell>
                                                    <TableCell align="right">
                                                        {audioFeatures.mode === 0
                                                            ? 'Minor'
                                                            : 'Major'}
                                                    </TableCell>
                                                </TableRow>
                                                <TableRow
                                                    key={'time_signature'}
                                                    style={{ cursor: 'pointer' }}
                                                >
                                                    <TableCell component="th" scope="row">
                                                        Time Signature (How many beats in each bar)
                                                    </TableCell>
                                                    <TableCell align="right">
                                                        {audioFeatures.time_signature}
                                                    </TableCell>
                                                </TableRow>
                                            </TableBody>
                                        </Table>
                                    </TableContainer>
                                </Grid>
                                <Grid xs={6} item sx={{ background: 'gray !important' }}>
                                    <RadarChart
                                        chartData={data}
                                        chartValues={audioFeatures}
                                        loading={playerState.loading}
                                        // positon={playerState.position}
                                    />
                                </Grid>
                                <Grid container xs={12}>
                                    <Layout />
                                </Grid>
                            </Grid>
                        </AccordionDetails>
                    </Accordion>
                </Grid>
                <ToastContainer />
            </AppBar>
        );
    }
}

export default connect(
    state => ({
        playerState: state.spotify.playerState,
        audioFeatures: state.spotify.audioFeatures,
        audioAnalysis: state.spotify.audioAnalysis,

        accessToken: state.spotify.accessToken,
        scenes: state.scenes.list,
        integrations: state.integrations.list.spotify,
    }),
    { updatePlayerState, getAsyncIntegrations, activateScene }
)(withStyles(styles)(SpotifyPlayer));
