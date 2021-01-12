import React, { Component } from 'react';
import { connect } from 'react-redux';
import { withStyles } from '@material-ui/core/styles';
import Grid from '@material-ui/core/Grid';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import CardHeader from '@material-ui/core/CardHeader';
import Button from '@material-ui/core/Button';
import CloudUploadIcon from '@material-ui/icons/CloudUpload';
import CloudDownloadIcon from '@material-ui/icons/CloudDownload';
import PowerSettingsNewIcon from '@material-ui/icons/PowerSettingsNew';

import { getAudioInputs, setAudioInput } from 'modules/settings';

import AudioInputCard from './AudioInput';
import ConfigCard from './ConfigCard';
import Divider from '@material-ui/core/Divider';

const styles = theme => ({});

class SettingsView extends Component {
    componentDidMount() {
        this.props.getAudioInputs();
    }

    render() {
        const { setAudioInput, settings } = this.props;
        const { audioInputs } = settings;

        return (
            <Grid container direction="column" spacing={4}>
                <Grid container item direction="row" spacing={4}>
                    <Grid item md={4}>
                        <AudioInputCard {...audioInputs} onChange={setAudioInput} />
                    </Grid>
                    <Grid item md={4}>
                        <ConfigCard settings={settings} />
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
    }
)(withStyles(styles)(SettingsView));
