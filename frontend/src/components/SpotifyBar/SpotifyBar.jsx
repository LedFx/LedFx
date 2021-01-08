import React, { Component } from 'react'
import PropTypes from "prop-types";
import { connect } from "react-redux";

import withStyles from "@material-ui/core/styles/withStyles";
import { AppBar, Button, Grid, Typography, Switch, FormControlLabel } from '@material-ui/core';
import {drawerWidth} from "frontend/assets/jss/style.jsx";
import TrackInfo from './TrackInfo';
import AddTrigger  from './AddTrigger';

import {getSpotifyEnabled }from 'frontend/actions'
import {getPresets} from 'frontend/actions';
import activatePreset from 'frontend/actions';

const styles = theme => ({
    appBar: {
        backgroundColor: '#333333',
        top: 'auto',
        bottom: 0,
        boxShadow: 'none',
        [theme.breakpoints.up('md')]: {
            left: `calc(${drawerWidth}px - 2px)`,
            width: `calc(100% - ${drawerWidth}px + 1vw)`
        }
    },
    loginBar: {
        paddingTop: '2vh',
        paddingBottom: '2vh'
    },
    spotifyLogin : {
        color:  '#333333',
    },
    connectedMessage: {
        color: "#FFFFFF"
    },
})

class SpotifyBar extends Component {
    constructor(props) {
        super(props);
        this.state = {
            token: null,
            showSpotify: true,
            trackState: null,
            trackPosition: 0,
            isPaused: true
        }
        this.toggleSpotify = this.toggleSpotify.bind(this);
        this.props.getSpotifyEnabled()
    }

    toggleSpotify() {
        if (this.state.showSpotify == true) {
            this.setState({showSpotify: false})
        } else {
            this.setState({showSpotify : true})
        }
    }

    spotifyLogin() {
        let scopes = encodeURIComponent('streaming user-read-email user-read-private');
        let client_id = 'a4d6df0f4b0047c2b23216c46bfc0f27'
        let redirect_uri = 'http://127.0.0.1:8888/dashboard/'

        window.location = [
            "https://accounts.spotify.com/authorize",
            `?client_id=${client_id}`,
            `&redirect_uri=${redirect_uri}`,
            `&scope=${scopes}`,
            "&response_type=token",
            "&show_dialog=true"
      ].join('');
    }

    getAccessToken() {
        // Grab the access token from Spotify after completing Spotify login
        var hash = window.location.hash.substr(1)
        console.log(hash)
        const accessToken = hash.split('&')[0].slice(13)
        return this.setState({
            token: accessToken
        })
    }

    initializePlayer() {
        // Make sure the 3rd-party Spotify script has loaded
        window.onSpotifyWebPlaybackSDKReady = () => {
            const token = this.state.token;
            const player = new Spotify.Player({
                name: 'LedFX Window',
                getOAuthToken: cb => {
                    cb(token);
                }
            });

            // Set up the web player
            player.addListener('initialization_error', ({ message }) => { console.error(message) });
            player.addListener('authentication_error', ({ message }) => { console.error(message) });
            player.addListener('account_error', ({ message }) => { console.error(message) });
            player.addListener('playback_error', ({ message }) => { console.error(message) });
            player.addListener('ready', ({ device_id }) => {console.log('Ready with Device ID', device_id)});
            player.addListener('not_ready', ({ device_id }) => {console.log('Device ID has gone offline', device_id)});

            // Listen for currently playing song changes
            player.addListener('player_state_changed', state => { this.handlePlayerStateChange(state) });

            player.connect();
        }
    }


    handlePlayerStateChange(state) {
        this.setState({trackState: state.track_window.current_track})
        this.setState({trackPosition: state.position})
        this.setState({isPaused: state.paused})
    }

    componentDidMount = () => {
        this.getAccessToken();
        this.initializePlayer();
    }

    render() {
        const {classes} = this.props;

        if (this.props.spotifyEnabled == false) {
            return null

        } else if (this.state.token === "") {
            return (
                <AppBar className={classes.appBar}>
                    <Grid container justify="center" alignItems="center" className={classes.loginBar}>
                        <Button  variant="contained" style={{backgroundColor: '#1ED760', color: '#FFFFFA'}}className={classes.spotifyLogin} onClick={this.spotifyLogin}>Log in with Spotify</Button>
                    </Grid>
                </AppBar>
            )
        } else if (this.state.trackState == null) {
            return (
                <AppBar className={classes.appBar}>
                    <Grid container justify='center'>
                        <Typography component="h3" className={classes.connectedMessage}>
                            Select "LedFX Window" using Spotify Connect!
                        </Typography>
                    </Grid>
                </AppBar>
            )
        }   else if (this.state.showSpotify == false) {
            return (
                <AppBar className={classes.appBar} style={{width:'12vw'}}>
                    <Grid container justify='center' alignItems='center'>
                        <Switch checked={this.state.showSpotify} onChange={() => this.toggleSpotify()}/>
                    </Grid>
                </AppBar>
            )
        } else return (
                <AppBar className={classes.appBar}>
                    <Grid container direction='row' justify="center" alignItems="center">
                        <Grid item container xs='12' sm='1' justify='center'>
                            <Switch checked={this.state.showSpotify} onChange={() => this.toggleSpotify()}/>
                        </Grid>
                        <Grid item xs='12' sm='3'>
                            <TrackInfo trackState={this.state.trackState} position={this.state.trackPosition} isPaused={this.state.isPaused}/>
                        </Grid>
                        <Grid item xs='12' sm='7'>
                            <AddTrigger trackState={this.state.trackState} position={this.state.trackPosition} />
                        </Grid>
                    </Grid>
                </AppBar>
            )
        }
    }


SpotifyBar.propTypes = {
  classes: PropTypes.object.isRequired
}

const mapStateToProps = state => ({
    spotifyEnabled: state.settings.spotifyEnabled
})

const mapDispatchToProps = (dispatch) => ({
    activatePreset: (presetId) => dispatch(activatePreset(presetId)),
    getPresets: () => dispatch(getPresets()),
    getSpotifyEnabled: () => dispatch(getSpotifyEnabled())
})

export default connect(mapStateToProps, mapDispatchToProps)(withStyles(styles)(SpotifyBar));
