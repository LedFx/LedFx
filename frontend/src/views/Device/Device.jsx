import React from 'react';
import PropTypes from 'prop-types';
import { connect } from 'react-redux';

import Grid from '@material-ui/core/Grid';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';

import { getDevice, getDeviceEffects } from 'proxies/device';
import EffectControl from 'components/EffectControl/EffectControl.jsx';
import PixelColorGraph from 'components/PixelColorGraph/PixelColorGraph.jsx';

class DeviceView extends React.Component {
    constructor() {
        super();
        this.state = {
            device: null,
            effect: null,
        };
    }

    componentDidMount() {
        const { device_id } = this.props.match.params;

        // this.state.device = null;
        getDevice(device_id)
            .then(response => {
                console.log('what the device here', response);
                this.setState({ device: response });
            })
            .catch(error => console.log(error));

        // this.state.effect = null;
        getDeviceEffects(device_id)
            .then(response => {
                this.setState({ effect: response.data });
            })
            .catch(error => console.log(error));
    }

    componentWillReceiveProps(nextProps) {
        var device = null;
        if (this.props.devicesById) {
            // this.state.device = null;
            console.log('whats going on here', this.props);
            device = this.props.devicesById[nextProps.match.params.device_id];
            this.setState({ device });
        }

        if (device !== undefined && device !== null) {
            // this.state.effect = null;
            getDeviceEffects(device.id)
                .then(response => {
                    this.setState({ effect: response.data });
                })
                .catch(error => console.log(error));
        }
    }

    render() {
        const { device, effect } = this.state;

        if (device) {
            return (
                <Grid container direction="row" spacing={4}>
                    {renderPixelGraph(device, effect)}
                    <Grid item xs={12}>
                        <Card>
                            <CardContent>
                                <EffectControl device={device} effect={effect} />
                            </CardContent>
                        </Card>
                    </Grid>
                </Grid>
            );
        }
        return <p>Loading</p>;
    }
}

const renderPixelGraph = (device, effect) => {
    if (device.effect && device.effect.name) {
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
    devicesById: PropTypes.object.isRequired,
};

function mapStateToProps(state) {
    const { devicesById } = state;

    return {
        devicesById,
    };
}

export default connect(mapStateToProps)(DeviceView);
