import React, { useEffect, useState } from 'react';
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
import { Responsive, WidthProvider } from 'react-grid-layout';
import "react-grid-layout/css/styles.css"
import "react-resizable/css/styles.css"
import { Fab } from '@material-ui/core';
import { Save } from '@material-ui/icons';
const ResponsiveGridLayout = WidthProvider(Responsive);
// let noob = 0


const useStyles = makeStyles(theme => ({
    root: {
        flexGrow: 1,
    },
    card: {
        width: '100%',
        height: '100%',
        overflowX: 'auto',
    },
    table: {
        width: '100%',
        maxWidth: '100%',
        backgroundColor: 'transparent',
        borderSpacing: '0',
    },
    '@global': {
        '.draghandler': {
            position: "absolute",
            width: "20px",
            height: "20px",
            right: 0,
            top: 0,
            cursor: 'move',
            '& > span': {
                position: "absolute",
                right: "3px",
                top: "3px",
                width: "5px",
                height: "5px",
                borderRight: "2px solid rgba(0, 0, 0, 0.4)",
                borderTop: "2px solid rgba(0, 0, 0, 0.4)",
            }
        },
        '.react-grid-item.react-grid-placeholder': {
            background: theme.palette.primary.main
        }
    }

}));


export const emptyObject = (data) => {
    let isEmpty = true;

    if (data && data !== 'undefined' && data !== null) {
        isEmpty = Object.keys(data).length === 0 && data.constructor === Object;
    }

    return isEmpty;
}


const DashboardView = () => {
    const devices = useSelector(state => state.devices);
    const displays = useSelector(state => state.displays);
    const scenes = useSelector(state => state.scenes);
    const classes = useStyles();
    const dispatch = useDispatch();
    const [layouts, setLayouts] = useState({})
    const getFromLS = (layoutName) => {
        if (window.localStorage) {
            let savedLayout = window.localStorage.getItem(layoutName);
            if (savedLayout && !emptyObject(savedLayout)) {
                setLayouts(JSON.parse(savedLayout).layouts)
                return JSON.parse(savedLayout).layouts;
            } else {
                // defaultLayout is defined elsewhere, when nothing in LocalStorage it's how it should be.
                return

            }
        }
    }
    const saveLayoutToLS = (layoutName, value) => {
        if (window.localStorage) {
            window.localStorage.setItem(layoutName, JSON.stringify({ layouts: value }));
        } else {
            console.error('localStorage is not supported');
        }
    }
    const onLayoutChange = (oldLayout, newLayout, test) => {
        // console.log("CHANGING", noob, layouts, oldLayout, newLayout)
        // if (oldLayout.length > 0) {
        //     if (noob > 2) {
        //         saveLayoutToLS("layouts", newLayout);
        //     }
        // }
        // noob = noob + 1
        setLayouts(newLayout);
    }

    useEffect(() => {
        dispatch(getScenes());
        dispatch(fetchDeviceList());
        dispatch(fetchDisplayList());
    }, [dispatch]);

    useEffect(() => {
        getFromLS("layouts")
    }, [displays]);

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
            <Fab
                color="primary"
                size="small"
                onClick={() => saveLayoutToLS("layouts", layouts)}
                style={{ position: "fixed", right: '6rem', top: '0.8rem', zIndex: 1100 }}

            >
                <Save />
            </Fab>
            <div style={{ position: "relative" }}>
                {displays && <ResponsiveGridLayout
                    draggableHandle={".draghandler"}
                    onLayoutChange={(oldLayout, newLayout) => onLayoutChange(oldLayout, newLayout)}
                    className="layout"
                    layouts={layouts}
                    breakpoints={{ lg: 1920, md: 996, sm: 768, xs: 480, xxs: 320 }}
                    cols={{ lg: 12, md: 10, sm: 6, xs: 4, xxs: 2 }} rowHeight={30}
                >
                    {displays.list.map((display, i) => (
                        <div data-grid={{ x: ((i % 4) * 3), y: 0, w: 3, h: 8, minW: 2, maxW: 12, minH: 8, maxH: 8 }} key={display.id}>
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
                                <span className={"draghandler"}> <span></span></span>
                            </Card>
                        </div>
                    ))}
                </ResponsiveGridLayout>}
            </div>
            {/* </Grid> */}
            <Grid container direction="row" spacing={4}>
                <Grid item sm={12} lg={6}>
                    <BladeMiniScenesCard />
                </Grid>
                <Grid item sm={12} lg={6}>
                    <AddSceneCard scenes={scenes} addScene={e => dispatch(addScene(e))} />
                </Grid>
            </Grid>
        </div >
    );
};

export default DashboardView;
