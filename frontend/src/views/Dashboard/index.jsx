import React from 'react';
import PropTypes from 'prop-types';
import { connect } from 'react-redux';
import withStyles from '@material-ui/core/styles/withStyles';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import Grid from '@material-ui/core/Grid';

import PixelColorGraph from 'components/PixelColorGraph';
import DeviceMiniControl from 'components/DeviceMiniControl';
import AddSceneCard from 'components/AddSceneCard';
import MiniScenesCard from 'components/MiniScenesCard';
import { addScene, getScenes, activateScene } from 'modules/scenes';
import { setDeviceEffect, clearDeviceEffect, fetchDeviceList } from 'modules/devices';
import { fetchDisplayList } from 'modules/displays';

const styles = theme => ({
    root: {
        flexGrow: 1,
    },
    card: {
        width: '100%',
        overflowX: 'auto',
    },
    table: {
        width: '100%',
        maxWidth: '100%',
        backgroundColor: 'transparent',
        borderSpacing: '0',
    },
});

class DashboardView extends React.Component {
    componentDidMount() {
        this.props.getScenes();
        this.props.fetchDeviceList();
        this.props.fetchDisplayList();
    }

    handleUpdateDeviceEffect = (deviceId, data) => {
        const { setDeviceEffect, clearDeviceEffect } = this.props;

        if (data.active) {
            setDeviceEffect(deviceId, data);
        } else {
            clearDeviceEffect(deviceId);
        }
    };

    render() {
        const { classes, devices, scenes, addScene, activateScene } = this.props;

        if (!devices.list.length) {
            return (
                <Card>
                    <CardContent>
                        <p>Looks like you have no devices! Go to 'Device Management' to add them</p>
                    </CardContent>
                </Card>
            );
        }

        return (
            <div>
                <Grid container direction="row" spacing={4}>
                    {devices.list.map(device => {
                        return (
                            <Grid key={device.id} item xs sm={6} lg={4} xl={3}>
                                <Card className={classes.card}>
                                    <CardContent>
                                        <DeviceMiniControl device={device} />
                                        <PixelColorGraph device={device} />
                                    </CardContent>
                                </Card>
                            </Grid>
                        );
                    })}
                </Grid>
                <Grid container direction="row" spacing={4}>
                    <Grid item sm>
                        <MiniScenesCard activateScene={activateScene} />
                    </Grid>
                    <Grid item sm>
                        <AddSceneCard scenes={scenes} addScene={addScene} />
                    </Grid>
                </Grid>
            </div>
        );
    }
}

DashboardView.propTypes = {
    devices: PropTypes.object.isRequired,
    scenes: PropTypes.object.isRequired,
};

export default connect(
    state => ({
        devices: state.devices,
        scenes: state.scenes,
    }),
    {
        addScene,
        activateScene,
        getScenes,
        setDeviceEffect,
        clearDeviceEffect,
        fetchDeviceList,
        fetchDisplayList,
    }
)(withStyles(styles)(DashboardView));
