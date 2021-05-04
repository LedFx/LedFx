import React, { useEffect, useState } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { Responsive, WidthProvider } from 'react-grid-layout';

import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

import { Save, WifiTethering } from '@material-ui/icons';

import { addScene, getScenes } from 'modules/scenes';
import { fetchDeviceList } from 'modules/devices';
import { fetchDisplayList } from 'modules/displays';
import { findWLEDDevices } from 'modules/devices';
import { setConfig } from 'modules/settings';

import Wled from 'components/CustomIcons/Wled';
import PixelColorGraph from 'components/PixelColorGraph';
import AddSceneCard from 'components/AddSceneCard';
import DisplayPixelColorGraph from 'components/PixelColorGraph/DisplayPixelColorGraph';
import BladeDeviceMiniControl from 'components/DeviceMiniControl/BladeDeviceMiniControl';
import BladeMiniScenesCard from 'components/MiniScenesCard/BladeMiniScenesCard';
import {
    Button,
    Card,
    CardContent,
    CircularProgress,
    Divider,
    Fab,
    FormControl,
    Grid,
    Icon,
    InputLabel,
    Link,
    makeStyles,
    MenuItem,
    Select,
} from '@material-ui/core';

const ResponsiveGridLayout = WidthProvider(Responsive);
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
    section: {
        display: 'flex',
        alignItems: 'flex-start',
        marginBottom: '1rem',
    },
    '@global': {
        '.draghandler': {
            position: 'absolute',
            width: '20px',
            height: '20px',
            right: 0,
            top: 0,
            cursor: 'move',
            '& > span': {
                position: 'absolute',
                right: '3px',
                top: '3px',
                width: '5px',
                height: '5px',
                borderRight: '2px solid rgba(0, 0, 0, 0.4)',
                borderTop: '2px solid rgba(0, 0, 0, 0.4)',
            },
        },
        '.react-grid-item.react-grid-placeholder': {
            background: theme.palette.primary.main,
        },
    },
}));

export const emptyObject = data => {
    let isEmpty = true;
    if (data && data !== 'undefined' && data !== null) {
        isEmpty = Object.keys(data).length === 0 && data.constructor === Object;
    }
    return isEmpty;
};

const DashboardView = () => {
    const devices = useSelector(state => state.devices);
    const displays = useSelector(state => state.displays);
    const scenes = useSelector(state => state.scenes);
    const settings = useSelector(state => state.settings);
    const classes = useStyles();
    const dispatch = useDispatch();
    const [layouts, setLayouts] = useState({});
    const [searchDevicesLoading, setSearchDevicesLoading] = useState(false);
    const handleFindDevices = () => {
        setSearchDevicesLoading(true);
        new Promise((resolve, reject) => {
            dispatch(findWLEDDevices({ resolve, reject, time: 30 }));
        }).then(() => {
            setSearchDevicesLoading(false);
        });
    };
    const onChangePreferredMode = value => {
        dispatch(setConfig({ config: { wled_preferences: {wled_preferred_mode:{preferred_mode: value, user_enabled: true }} }}));
    };
    const onChangeStartupScan = value => {
        dispatch(setConfig({ config: { scan_on_startup: value } }));
    };
    const getFromLS = layoutName => {
        if (window.localStorage) {
            let savedLayout = window.localStorage.getItem(layoutName);
            if (savedLayout && !emptyObject(savedLayout)) {
                setLayouts(JSON.parse(savedLayout).layouts);
                return JSON.parse(savedLayout).layouts;
            } else {
                // defaultLayout is defined elsewhere, when nothing in LocalStorage it's how it should be.
                return;
            }
        }
    };
    const saveLayoutToLS = (layoutName, value) => {
        if (window.localStorage) {
            window.localStorage.setItem(layoutName, JSON.stringify({ layouts: value }));
        } else {
            console.error('localStorage is not supported');
        }
    };
    const onLayoutChange = (oldLayout, newLayout, test) => {
        // console.log("CHANGING", noob, layouts, oldLayout, newLayout)
        // if (oldLayout.length > 0) {
        //     if (noob > 2) {
        //         saveLayoutToLS("layouts", newLayout);
        //     }
        // }
        // noob = noob + 1
        setLayouts(newLayout);
    };

    useEffect(() => {
        dispatch(getScenes());
        dispatch(fetchDeviceList());
        dispatch(fetchDisplayList());
    }, [dispatch]);

    useEffect(() => {
        getFromLS('layouts');
    }, [displays]);

    if (!devices.list.length) {
        return (
            <Grid container item xs={12} sm={9} md={9} lg={6} xl={4} spacing={3}>
                <Grid item xs={12} sm={12} md={12} lg={12} xl={12}>
                    <Card>
                        <CardContent>
                            <div className={classes.section}>
                                <Icon
                                    fontSize={'large'}
                                    style={{ marginRight: '1rem', marginTop: '0.5rem' }}
                                >
                                    info
                                </Icon>
                                <div>
                                    <h2 style={{ margin: 0 }}>Looks like you have no devices!</h2>
                                    <p style={{ marginTop: 0 }}>
                                        If you have just starting using LedFx, make sure to check
                                        the
                                        <Link
                                            href={'https://ledfx.readthedocs.io/en/master/'}
                                            style={{ marginLeft: '.5rem' }}
                                        >
                                            <Button variant={'outlined'} size={'small'}>
                                                docs
                                            </Button>
                                        </Link>
                                    </p>
                                </div>
                            </div>

                            <Divider />
                            <div className={classes.section}>
                                <Icon
                                    style={{
                                        margin: '0.5rem',
                                        marginTop: '1rem',
                                        marginRight: '1rem',
                                    }}
                                >
                                    <Wled />
                                </Icon>
                                <h2>WLED-Integration</h2>
                            </div>
                            <div
                                style={{
                                    marginLeft: '2.5rem',
                                    display: 'flex',
                                    flexDirection: 'column',
                                }}
                            >
                                <FormControl>
                                    <InputLabel id="wled-scan-selector">
                                        Scan for WLED on startup
                                    </InputLabel>
                                    <Select
                                        labelId="wled-scan-selector"
                                        id="wled-scan-select"
                                        value={settings.scan_on_startup}
                                        onChange={e => onChangeStartupScan(e.target.value)}
                                    >
                                        <MenuItem value={true}>Yes</MenuItem>
                                        <MenuItem value={false}>No</MenuItem>
                                    </Select>
                                </FormControl>
                                <FormControl>
                                    <InputLabel id="wled-mode-selector">
                                        Preferred WLED mode
                                    </InputLabel>
                                    <Select
                                        labelId="wled-mode-selector"
                                        id="wled-mode-select"
                                        value={settings.wled_preferred_mode}
                                        onChange={e => onChangePreferredMode(e.target.value)}
                                    >
                                        <MenuItem value={'unset'}>Unset</MenuItem>
                                        <MenuItem value={'E131'}>E131</MenuItem>
                                        <MenuItem value={'DDP'}>DDP</MenuItem>
                                    </Select>
                                </FormControl>
                                <div
                                    style={{
                                        marginTop: '2rem',
                                        textAlign: 'right',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'flex-end',
                                    }}
                                >
                                    <div style={{ display: 'flex', alignItems: 'center' }}>
                                        {searchDevicesLoading && (
                                            <CircularProgress
                                                variant="determinate"
                                                value={(devices.scanProgress / 30) * 100}
                                                size={35}
                                                style={{ marginRight: '0.5rem' }}
                                            />
                                        )}
                                        <Button
                                            variant={'outlined'}
                                            aria-label="Scan"
                                            disabled={searchDevicesLoading}
                                            onClick={handleFindDevices}
                                            endIcon={<WifiTethering />}
                                        >
                                            Find WLEDs
                                        </Button>
                                    </div>
                                    <Link href={`/devices`} style={{ marginLeft: '.5rem' }}>
                                        <Button variant={'outlined'}>Device Management</Button>
                                    </Link>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>
        );
    }

    return (
        <div>
            <Fab
                color="primary"
                size="small"
                onClick={() => saveLayoutToLS('layouts', layouts)}
                style={{ position: 'fixed', right: '6rem', top: '0.8rem', zIndex: 1100 }}
            >
                <Save />
            </Fab>
            <div style={{ position: 'relative' }}>
                {displays && (
                    <ResponsiveGridLayout
                        draggableHandle={'.draghandler'}
                        onLayoutChange={(oldLayout, newLayout) =>
                            onLayoutChange(oldLayout, newLayout)
                        }
                        className="layout"
                        layouts={layouts}
                        breakpoints={{ lg: 1920, md: 996, sm: 768, xs: 480, xxs: 320 }}
                        cols={{ lg: 12, md: 10, sm: 6, xs: 4, xxs: 2 }}
                        rowHeight={30}
                    >
                        {displays.list.map((display, i) => (
                            <div
                                data-grid={{
                                    x: (i % 4) * 3,
                                    y: 0,
                                    w: 3,
                                    h: 8,
                                    minW: 2,
                                    maxW: 12,
                                    minH: 8,
                                    maxH: 8,
                                }}
                                key={display.id}
                            >
                                <Card className={classes.card}>
                                    <CardContent>
                                        <BladeDeviceMiniControl device={display} />
                                        {display.is_device &&
                                        devices.list.find(d => d.id === display.is_device) &&
                                        devices.list.find(d => d.id === display.is_device)
                                            .active_displays.length > 0 ? (
                                            <PixelColorGraph
                                                device={devices.list.find(
                                                    d => d.id === display.is_device
                                                )}
                                            />
                                        ) : display.active ? (
                                            <DisplayPixelColorGraph
                                                pause={
                                                    devices.list.find(
                                                        d => d.id === display.is_device
                                                    ) &&
                                                    devices.list.find(
                                                        d => d.id === display.is_device
                                                    ).active_displays.length > 0
                                                }
                                                display={display}
                                            />
                                        ) : (
                                            <DisplayPixelColorGraph
                                                pause={
                                                    devices.list.find(
                                                        d => d.id === display.is_device
                                                    ) &&
                                                    devices.list.find(
                                                        d => d.id === display.is_device
                                                    ).active_displays.length > 0
                                                }
                                                display={display}
                                            />
                                        )}
                                    </CardContent>
                                    <span className={'draghandler'}>
                                        {' '}
                                        <span></span>
                                    </span>
                                </Card>
                            </div>
                        ))}
                    </ResponsiveGridLayout>
                )}
            </div>

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
