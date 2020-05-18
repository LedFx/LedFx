import React from 'react';
import withStyles from '@material-ui/core/styles/withStyles';

import { connect } from 'react-redux';

import Grid from '@material-ui/core/Grid';

import PresetsCard from 'components/PresetCard/PresetCard.jsx';
import AddPresetCard from 'components/AddPresetCard/AddPresetCard';
import { getPresets } from 'actions';
import { includeKeyInObject } from 'utils/helpers';

const styles = theme => ({
    cardResponsive: {
        width: '100%',
        overflowX: 'auto',
    },
    button: {
        position: 'absolute',
        bottom: theme.spacing.unit * 2,
        right: theme.spacing.unit * 2,
    },
    dialogButton: {
        float: 'right',
    },
});

class PresetsView extends React.Component {
    componentDidMount = () => {
        this.props.getPresets();
    };

    render() {
        return (
            <div>
                <Grid container direction="row" spacing={4}>
                    <Grid item xs={12}>
                        <AddPresetCard />
                    </Grid>
                    <Grid item xs={12}>
                        <React.Fragment>{renderPresets(this.props.presets)}</React.Fragment>
                    </Grid>
                </Grid>
            </div>
        );
    }
}

const renderPresets = presets =>
    Object.keys(presets).map(key => (
        <PresetsCard key={key} preset={includeKeyInObject(key, presets[key])} />
    ));

const mapStateToProps = state => ({
    presets: state.presets,
});

const mapDispatchToProps = dispatch => ({
    getPresets: () => dispatch(getPresets()),
});

export default connect(mapStateToProps, mapDispatchToProps)(withStyles(styles)(PresetsView));
