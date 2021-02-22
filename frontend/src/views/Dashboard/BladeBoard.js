import React, { useEffect } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { makeStyles } from '@material-ui/core/styles';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import Grid from '@material-ui/core/Grid';
import PixelColorGraph from 'components/PixelColorGraph';
import AddSceneCard from 'components/AddSceneCard';
import { addScene, getScenes } from 'modules/scenes';
import { fetchDeviceList } from 'modules/devices';
import { fetchDisplayList } from 'modules/displays';
import DisplayPixelColorGraph from 'components/PixelColorGraph/DisplayPixelColorGraph';
import BladeDeviceMiniControl from 'components/DeviceMiniControl/BladeDeviceMiniControl';
import BladeMiniScenesCard from 'components/MiniScenesCard/BladeMiniScenesCard';

const useStyles = makeStyles(theme => ({
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
}));

const DashboardView = () => {
    const devices = useSelector(state => state.devices);
    const displays = useSelector(state => state.displays);
    const scenes = useSelector(state => state.scenes);
    const classes = useStyles();
    const dispatch = useDispatch();

    useEffect(() => {
        dispatch(getScenes());
        dispatch(fetchDeviceList());
        dispatch(fetchDisplayList());
    }, [dispatch]);

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
            <Grid container direction="row-reverse" justify="flex-end" spacing={4}>
                {displays.list.map(display => (
                    <Grid key={display.id} item sm={12} lg={6} xl={3}>
                        <Card className={classes.card}>
                            <CardContent>
                                <BladeDeviceMiniControl device={display} />
                                {display.is_device &&
                                devices.list.find(d => d.id === display.is_device) &&
                                devices.list.find(d => d.id === display.is_device).active_displays
                                    .length > 0 ? (
                                    <PixelColorGraph
                                        device={devices.list.find(d => d.id === display.is_device)}
                                    />
                                ) : display.active ? (
                                    <DisplayPixelColorGraph
                                        pause={
                                            devices.list.find(d => d.id === display.is_device) &&
                                            devices.list.find(d => d.id === display.is_device)
                                                .active_displays.length > 0
                                        }
                                        display={display}
                                    />
                                ) : (
                                    <DisplayPixelColorGraph
                                        pause={
                                            devices.list.find(d => d.id === display.is_device) &&
                                            devices.list.find(d => d.id === display.is_device)
                                                .active_displays.length > 0
                                        }
                                        display={display}
                                    />
                                )}
                            </CardContent>
                        </Card>
                    </Grid>
                ))}
            </Grid>
            <Grid container direction="row" spacing={4}>
                <Grid item sm={12} lg={6}>
                    <BladeMiniScenesCard />
                </Grid>
                <Grid item sm={12} lg={6}>
                    <AddSceneCard scenes={scenes} addScene={e => dispatch(addScene(e))} />
                </Grid>
            </Grid>
        </div>
    );
};

export default DashboardView;
