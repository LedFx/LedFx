import React from 'react';
import PropTypes from 'prop-types';
import { connect } from 'react-redux';

import Grid from '@material-ui/core/Grid';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';

import { loadDeviceInfo, setDeviceEffect, clearDeviceEffect } from 'modules/selectedDevice';
import { activatePreset, getDevicePresets, addPreset } from 'modules/presets';
import EffectControl from 'components/EffectControl';
import PixelColorGraph from 'components/PixelColorGraph';
import PresetsCard from 'components/PresetsCard';

class DeviceView extends React.Component {
    componentDidMount() {
        const { deviceId } = this.props.match.params;
        this.handleLoadDevice(deviceId);
    }

    componentWillReceiveProps(nextProps) {
        const { deviceId } = this.props.match.params;
        const { deviceId: newDeviceId } = nextProps.match.params;
        if (deviceId !== newDeviceId) {
            this.handleLoadDevice(newDeviceId);
        }
    }

    handleLoadDevice = deviceId => {
        const { loadDeviceInfo } = this.props;
        loadDeviceInfo(deviceId);
    };

    handleClearEffect = deviceId => {
        const { clearDeviceEffect } = this.props;
        clearDeviceEffect(deviceId);
    };

    handleSetEffect = data => {
        const { setDeviceEffect } = this.props;
        console.log('handle submite devcice data', data);
        setDeviceEffect(data.deviceId, data);
    };

    render() {
        const {
            presets,
            schemas,
            selectedDevice,
            activatePreset,
            getDevicePresets,
            addPreset,
        } = this.props;
        const { device, effect, isDeviceLoading, isEffectLoading } = selectedDevice;

        if (schemas.isLoading || isDeviceLoading || isEffectLoading || !device || !effect) {
            return <p>Loading</p>;
        }

        return (
            <Grid container direction="row" spacing={4}>
                {renderPixelGraph(device, effect)}
                <Grid item xs={6}>
                    <Card>
                        <CardContent>
                            <EffectControl
                                device={device}
                                effect={effect}
                                schemas={schemas}
                                onClear={this.handleClearEffect}
                                onSubmit={this.handleSetEffect}
                            />
                        </CardContent>
                    </Card>
                </Grid>
                <Grid item xs={6}>
                    {effect.type && (
                        <PresetsCard
                            device={device}
                            presets={presets}
                            activatePreset={activatePreset}
                            getDevicePresets={getDevicePresets}
                            addPreset={addPreset}
                        />
                    )}
                </Grid>
            </Grid>
        );
    }
}

const renderPixelGraph = (device, effect) => {
    if (device && effect?.name) {
        return (
            <Grid item xs={12}>
                <Card>
                    <CardContent>
                        <PixelColorGraph device={device} />
                    </CardContent>
                </Card>
            </Grid>
        );
    }
};

DeviceView.propTypes = {
    schemas: PropTypes.object.isRequired,
    selectedDevice: PropTypes.object.isRequired,
};

export default connect(
    state => ({
        schemas: state.schemas,
        selectedDevice: state.selectedDevice,
        presets: state.presets,
    }),
    {
        loadDeviceInfo,
        clearDeviceEffect,
        setDeviceEffect,
        activatePreset,
        getDevicePresets,
        addPreset,
    }
)(DeviceView);
