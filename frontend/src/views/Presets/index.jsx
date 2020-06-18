import React from 'react';
import { connect } from 'react-redux';

import withStyles from '@material-ui/core/styles/withStyles';
import Grid from '@material-ui/core/Grid';
import CircularProgress from '@material-ui/core/CircularProgress';

import PresetsCard from 'components/PresetCard';
import AddPresetCard from 'components/AddPresetCard';
import { getPresets, addPreset, activatePreset, deletePreset } from 'modules/presets';

const styles = theme => ({
    cardResponsive: {
        width: '100%',
        overflowX: 'auto',
    },
    button: {
        position: 'absolute',
        bottom: theme.spacing(2),
        right: theme.spacing(2),
    },
    dialogButton: {
        float: 'right',
    },
    spinnerContainer: {
        height: '10rem',
    },
});

class PresetsView extends React.Component {
    componentDidMount() {
        this.props.getPresets();
    }

    render() {
        const { presets, classes, deletePreset, activatePreset } = this.props;
        console.log('whats the presets main props', presets);

        return (
            <Grid container direction="row" spacing={4}>
                <Grid item xs={12}>
                    <AddPresetCard presets={presets} addPreset={addPreset} />
                </Grid>
                {presets.isLoading ? (
                    <Grid
                        container
                        justify="center"
                        alignContent="center"
                        className={classes.spinnerContainer}
                    >
                        <CircularProgress size={80} />
                    </Grid>
                ) : (
                    presets.list.map(preset => (
                        <Grid item xs={12} md={6}>
                            <PresetsCard
                                key={preset.id}
                                preset={preset}
                                deletePreset={deletePreset}
                                activatePreset={activatePreset}
                            />
                        </Grid>
                    ))
                )}
            </Grid>
        );
    }
}

export default connect(
    state => ({
        presets: state.presets,
    }),
    { getPresets, addPreset, activatePreset, deletePreset }
)(withStyles(styles)(PresetsView));
