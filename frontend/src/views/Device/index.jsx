import React from 'react';
import PropTypes from 'prop-types';
import { connect } from 'react-redux';

import Grid from '@material-ui/core/Grid';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import Typography from '@material-ui/core/Typography';

import { loadDeviceInfo, setDeviceEffect, clearDeviceEffect } from 'modules/selectedDevice';
import { fetchDeviceList } from 'modules/devices';
import { fetchDisplayList } from 'modules/displays';
import { activatePreset, getEffectPresets, addPreset } from 'modules/presets';
// import EffectControl from 'components/EffectControl';
// import EffectControlBlade from 'components/EffectControl/blade';
import PixelColorGraph from 'components/PixelColorGraph';
// import PresetsCard from 'components/PresetsCard';

class DeviceView extends React.Component {
    componentDidMount() {
        const { deviceId } = this.props.match.params;
        this.handleLoadDevice(deviceId);
        this.props.fetchDeviceList();
        this.props.fetchDisplayList();
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
        setDeviceEffect(data.deviceId, data);
    };

    handleTypeChange = effectType => {
        const { getEffectPresets } = this.props;
        getEffectPresets(effectType);
    };

    render() {
        const {
            devices,
            presets,
            schemas,
            selectedDevice,
            activatePreset,
            getEffectPresets,
            addPreset,
        } = this.props;
        const { device, effect, isDeviceLoading, isEffectLoading } = selectedDevice;

        if (schemas.isLoading || isDeviceLoading || !device) {
            return <p>Loading</p>;
        }
        console.log(
            'GG:',
            devices.find(d => d.id === device.id),
            device
        );
        if (
            devices.find(d => d.id === device.id) &&
            !devices.find(d => d.id === device.id).displays
        ) {
            return (
                <Card>
                    <CardContent>
                        <PixelColorGraph device={device} />
                    </CardContent>
                </Card>
                // <Grid container direction="row" spacing={4}>
                //     {renderPixelGraph(device, effect)}
                //     <Grid item xs={12} lg={6}>
                //         <Card>
                //             <CardContent>
                //                 <EffectControl
                //                     device={device}
                //                     effect={effect}
                //                     schemas={schemas}
                //                     onClear={this.handleClearEffect}
                //                     onSubmit={this.handleSetEffect}
                //                     onTypeChange={this.handleTypeChange}
                //                 />
                //             </CardContent>
                //         </Card>
                //     </Grid>
                //     <Grid item xs={12} lg={6}>
                //         {effect.type && (
                //             <PresetsCard
                //                 device={device}
                //                 presets={presets}
                //                 effect={effect}
                //                 activatePreset={activatePreset}
                //                 getEffectPresets={getEffectPresets}
                //                 addPreset={addPreset}
                //             />
                //         )}
                //     </Grid>
                //     {parseInt(window.localStorage.getItem('BladeMod')) > 2 && (
                //         <Grid item xs={12} lg={6}>
                //             <Card>
                //                 <CardContent>
                //                     <EffectControlBlade
                //                         device={device}
                //                         effect={effect}
                //                         schemas={schemas}
                //                         onClear={this.handleClearEffect}
                //                         onSubmit={this.handleSetEffect}
                //                         onTypeChange={this.handleTypeChange}
                //                     />
                //                 </CardContent>
                //             </Card>
                //         </Grid>
                //     )}
                // </Grid>
            );
        }
        return (
            <>
                <Card>
                    <CardContent>
                        <PixelColorGraph device={device} />
                    </CardContent>
                </Card>
                <Card style={{ marginTop: '2rem' }}>
                    <CardContent>
                        <Typography variant="h5">Displays</Typography>

                        <Typography color="textSecondary">
                            These displays are outputting to this device:
                        </Typography>
                        <ul>
                            {devices.find(d => d.id === device.id) &&
                                devices
                                    .find(d => d.id === device.id)
                                    .displays.map(display => <li key={display}>{display}</li>)}
                        </ul>
                    </CardContent>
                </Card>
            </>
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
        devices: state.devices.list,
    }),
    {
        loadDeviceInfo,
        clearDeviceEffect,
        setDeviceEffect,
        activatePreset,
        getEffectPresets,
        addPreset,
        fetchDeviceList,
        fetchDisplayList,
    }
)(DeviceView);
