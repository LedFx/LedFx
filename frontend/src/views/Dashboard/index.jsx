import React from 'react';
import PropTypes from 'prop-types';
import { connect } from 'react-redux';
import withStyles from '@material-ui/core/styles/withStyles';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
<<<<<<< HEAD:frontend/src/views/Dashboard/index.jsx
import Grid from '@material-ui/core/Grid';

import PixelColorGraph from 'components/PixelColorGraph';
import DeviceMiniControl from 'components/DeviceMiniControl';
import AddPresetCard from 'components/AddPresetCard';
import { addPreset, getPresets } from 'modules/presets';
import { setDeviceEffect, clearDeviceEffect } from 'modules/devices';
=======

import Grid from "@material-ui/core/Grid";
import PixelColorGraph from "frontend/components/PixelColorGraph/PixelColorGraph.jsx";
import DeviceMiniControl from 'frontend/components/DeviceMiniControl/DeviceMiniControl.jsx';
import AddSceneCard from "frontend/components/AddSceneCard/AddSceneCard";
import MiniScenesCard from "frontend/components/MiniScenesCard/MiniScenesCard";

>>>>>>> dev:ledfx/frontend/views/Dashboard/Dashboard.jsx

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
        this.props.getPresets();
    }

    handleUpdateDeviceEffect = (deviceId, data) => {
        const { setDeviceEffect, clearDeviceEffect } = this.props;

<<<<<<< HEAD:frontend/src/views/Dashboard/index.jsx
        console.log('what the dashoboard checkker', data, deviceId);
        if (data.active) {
            setDeviceEffect(deviceId, data);
        } else {
            clearDeviceEffect(deviceId);
        }
    };
=======
    if (Object.keys(devicesById) == 0)
    {
      return (
        <div>
          <Card variant="outlined">
              <CardContent>
                <p>Looks like you have no devices! Go to 'Device Management' to add them</p>
              </CardContent>
          </Card>
        </div>
      );
    }
>>>>>>> dev:ledfx/frontend/views/Dashboard/Dashboard.jsx

    render() {
        const { classes, devices, presets, addPreset } = this.props;

<<<<<<< HEAD:frontend/src/views/Dashboard/index.jsx
        if (!devices.list.length) {
            return (
                <Card>
=======
        <Grid container direction="row" spacing={4}>
          {
            Object.keys(devicesById).map(id => {                      
              return (
                <Grid item lg={6}>
                  <Card className={classes.card} variant="outlined">
>>>>>>> dev:ledfx/frontend/views/Dashboard/Dashboard.jsx
                    <CardContent>
                        <p>Looks like you have no devices! Go to 'Device Management' to add them</p>
                    </CardContent>
                </Card>
            );
        }

<<<<<<< HEAD:frontend/src/views/Dashboard/index.jsx
        return (
            <div>
                <Grid container direction="row" spacing={4}>
                    {devices.list.map(device => {
                        return (
                            <Grid key={device.id} item lg={6}>
                                <Card className={classes.card}>
                                    <CardContent>
                                        <Grid container direction="row" spacing={1}>
                                            <Grid item xs={12}>
                                                <DeviceMiniControl
                                                    device={device}
                                                    setDeviceEffect={this.handleUpdateDeviceEffect}
                                                />
                                            </Grid>
                                            <Grid item xs={12}>
                                                <PixelColorGraph device={device} />
                                            </Grid>
                                        </Grid>
                                    </CardContent>
                                </Card>
                            </Grid>
                        );
                    })}
                </Grid>
                <Grid container direction="row" spacing={4}>
                    <Grid item xs={12}>
                        <AddPresetCard presets={presets} addPreset={addPreset} />
                    </Grid>
                </Grid>
            </div>
        );
    }
=======
        <Grid container direction="row" spacing={4} alignItems="stretch">
          <Grid item xs={6}>
            <MiniScenesCard />
          </Grid>
          <Grid item xs={6}>
            <AddSceneCard />
          </Grid>
        </Grid>
      </div>
    );
  }
>>>>>>> dev:ledfx/frontend/views/Dashboard/Dashboard.jsx
}

DashboardView.propTypes = {
    devices: PropTypes.object.isRequired,
    presets: PropTypes.object.isRequired,
};

export default connect(
    state => ({
        devices: state.devices,
        presets: state.presets,
    }),
    { addPreset, getPresets, setDeviceEffect, clearDeviceEffect }
)(withStyles(styles)(DashboardView));
