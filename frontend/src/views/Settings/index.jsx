import React, { Component } from 'react';
import { connect } from 'react-redux';
import { withStyles } from '@material-ui/core/styles';
import Grid from '@material-ui/core/Grid';

import { getAudioInputs, setAudioInput } from 'modules/settings';

import AudioInputCard from './AudioInput';
import ConfigCard from './ConfigCard';
import LogCard from './LogCard';
import ThemesCard from './ThemesCard';
import { fetchDisplayList } from 'modules/displays';

const styles = theme => ({});

class SettingsView extends Component {
    componentDidMount() {
        this.props.getAudioInputs();
        this.props.fetchDisplayList();
    }

    render() {
        const { setAudioInput, settings } = this.props;
        const { audioInputs } = settings;

        return (
            <Grid container direction="column" spacing={4} style={{ overflow: 'hidden' }}>
                <Grid container item direction="row" spacing={4}>
                    <Grid item md={4}>
                        <AudioInputCard {...audioInputs} onChange={setAudioInput} />
                    </Grid>
                    <Grid item md={4}>
                        <ThemesCard />
                    </Grid>
                    <Grid item md={4}>
                        <ConfigCard settings={settings} />
                    </Grid>
                    <Grid item md={12}>
                        <LogCard />
                    </Grid>
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
        fetchDisplayList,
    }
)(withStyles(styles)(SettingsView));
