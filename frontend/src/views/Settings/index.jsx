import React, { Component } from 'react';
import { connect } from 'react-redux';
import { withStyles } from '@material-ui/core/styles';
import Grid from '@material-ui/core/Grid';

import { getAudioInputs, setAudioInput } from 'modules/settings';

import AudioInputCard from './AudioInput';
import ConfigCard from './ConfigCard';
import LogCard from './LogCard';

const styles = theme => ({});

class SettingsView extends Component {
    componentDidMount() {
        this.props.getAudioInputs();
    }

    render() {
        const { setAudioInput, settings } = this.props;
        const { audioInputs } = settings;

        return (
            <Grid container direction="row" spacing={4}>
                <Grid item xs={3}>
                    <AudioInputCard {...audioInputs} onChange={setAudioInput} />
                </Grid>
                <Grid item xs={3}>
                    <ConfigCard settings={settings} />
                </Grid>
                <Grid item xs={12}>
                    <LogCard></LogCard>
                </Grid>
            </Grid>
        );
    }
}

export default connect(
    state => ({
        settings: state.settings,
    }),
    {
        getAudioInputs,
        setAudioInput,
    }
)(withStyles(styles)(SettingsView));
