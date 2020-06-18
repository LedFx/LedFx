import React from 'react';
import PropTypes from 'prop-types';
import { connect } from 'react-redux';

import Grid from '@material-ui/core/Grid';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';

import { loadDeviceInfo, setDeviceEffect, clearDeviceEffect } from 'modules/selectedDevice';
import EffectControl from 'components/EffectControl';
import PixelColorGraph from 'components/PixelColorGraph';

class DeviceView extends React.Component {
    componentDidMount() {
        console.log('component did mount device', this.props.match.params);
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
        console.log('what this data in Devices page', data);
        setDeviceEffect(data);
    };

    render() {
        const { schemas, selectedDevice } = this.props;
        const { device, effect, isDeviceLoading, isEffectLoading } = selectedDevice;

        if (schemas.isLoading || isDeviceLoading || isEffectLoading) {
            return <p>Loading</p>;
        }
        return (
            <Grid container direction="row" spacing={4}>
                {renderPixelGraph(device, effect)}
                <Grid item xs={12}>
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
            </Grid>
        );
    }
}

const renderPixelGraph = (device, effect) => {
    if (device && effect?.name) {
        console.log(effect);
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
    }),
    { loadDeviceInfo, clearDeviceEffect, setDeviceEffect }
)(DeviceView);
