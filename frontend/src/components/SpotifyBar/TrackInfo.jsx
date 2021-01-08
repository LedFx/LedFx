import React, { Component } from 'react'
import { connect } from "react-redux";

import withStyles from "@material-ui/core/styles/withStyles";
import { Grid, Snackbar } from '@material-ui/core'
import MuiAlert from '@material-ui/lab/Alert';

import {getPresets, activatePreset} from 'frontend/actions'

const styles = theme => ({
    outer: {
        paddingLeft: '1vw'
    },
    songTitle: {
        color: '#1ED760',
        marginBottom: 2
    },
    albumName: {
        marginTop: 0,
        color: '#1ED760'
    },
    positionText: {
        color: '#1ED760',
        margin: 0
    }
})

class TrackInfo extends Component {
    constructor(props) {
        super(props);
        this.state = {
            trackName: '',
            activatedPreset: '',
            messageOpen: false
        }
    }

    checkForTriggers() {
        const presetsObject = this.props.presets
        let mostRecentTriggerPosition = 0
        let presetToActivate = null
        let presetsToCountdown = []

        for (const preset in presetsObject) {
            const triggersObject = presetsObject[preset].triggers

            for (const trigger in triggersObject) {
                const triggerSongID = triggersObject[trigger][0]
                let triggerSongPosition = triggersObject[trigger][2]

                if (triggerSongPosition == null) {
                    triggerSongPosition = 0
                }

                if (triggerSongID == this.props.trackState.id) {

                    if (this.props.position >= triggerSongPosition && triggerSongPosition >= mostRecentTriggerPosition) {
                        mostRecentTriggerPosition = triggerSongPosition
                        presetToActivate = preset
                    } else if (this.props.position < triggerSongPosition) {
                        presetsToCountdown.push([preset, triggerSongPosition])
                    }
                }
            }
        }

        presetsToCountdown.forEach( (trigger) => {
            // trigger[0] = presetID
            // trigger[1] = songPosition
            setTimeout( () => {
                this.props.activatePreset(trigger[0])
                this.setState({activatedPreset: trigger[0], messageOpen: true})
            }, trigger[1] - this.props.position)
        })

        if (presetToActivate != null && presetToActivate != this.state.activatedPreset) {
            this.props.activatePreset(presetToActivate)
            this.setState({activatedPreset: presetToActivate, messageOpen: true})
        }
    }

    componentDidMount() {
        this.props.getPresets()
    }

    componentDidUpdate(prevProps) {
        if (prevProps != this.props && this.props.isPaused == false) {
            this.checkForTriggers()
        }
    }

    render() {
        const {classes, trackState, position} = this.props

        return (
            <div>
                <Snackbar onClose={() => this.setState({messageOpen: false})} open={this.state.messageOpen} autoHideDuration={2000}>
                    <MuiAlert onClose={() => this.setState({messageOpen: false})} elevation={6} variant="filled" severity='success'>Activated Preset: {this.state.activatedPreset}</MuiAlert>
                </Snackbar>
                <Grid container direction='row' className={classes.outer}>
                    <Grid item xs='9' container direction='column' justify='center' alignItems='flex-start'>
                        <h4 className={classes.songTitle}>{trackState.name}</h4>
                        <p className={classes.albumName}>{trackState.artists[0].name}</p>
                    </Grid>
                    <Grid item xs='3' container direction='column' justify='center' alignItems='center'>
                        <p className={classes.positionText}>Position</p>
                        <p className={classes.positionText}>{position}</p>
                    </Grid>
                </Grid>
            </div>
        )
    }
}

const mapStateToProps = state => ({
    presets: state.presets
})

const mapDispatchToProps = (dispatch) => ({
    getPresets: () => dispatch(getPresets()),
    activatePreset: (id) => dispatch(activatePreset(id))
})

export default connect(mapStateToProps, mapDispatchToProps)(withStyles(styles)(TrackInfo));
