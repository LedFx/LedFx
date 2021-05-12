import React from 'react';
import Grid from '@material-ui/core/Grid';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import Typography from '@material-ui/core/Typography';
import { Button, CircularProgress, Divider, Icon, Popover } from '@material-ui/core';
import NetworkCheckIcon from '@material-ui/icons/NetworkCheck';
import { makeStyles } from '@material-ui/core/styles';
import * as displayProxies from 'proxies/display';
import { getDevice } from 'proxies/device';
import Wled from 'components/CustomIcons/Wled';
import Moment from 'react-moment';
import moment from 'moment';

const useStyles = makeStyles(theme => ({
    title: {
        color: theme.palette.text.secondary,
    },
}));

const MoreInfo = ({ display }) => {
    // console.log(display);
    const classes = useStyles();
    const [anchorEl, setAnchorEl] = React.useState();
    const [pingData, setPingData] = React.useState();
    const [wledData, setWledData] = React.useState();

    const handleClick = event => {
        ping();
        setAnchorEl(event.currentTarget);
    };

    const handleClose = () => {
        setAnchorEl(null);
        setPingData(null);
    };
    const ping = async () => {
        try {
            const response = await displayProxies.getPing(display.id);
            const wledResponse = await getDevice(display.id);
            const ip = wledResponse.config.ip_address;
            await fetch(`http://${ip}/json/info`)
                .then(res => res.json())
                .then(res => setWledData(res))
                .catch(err => console.error(err));

            if (response.statusText === 'OK') {
                setPingData(response.data);
            }
        } catch (error) {
            console.log('Error pinging display', error.message);
        }
    };
    console.log('YZ0', pingData, wledData);
    return (
        <>
            <Grid item xs={6} lg={6}>
                <Card>
                    <CardContent>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <Typography variant="h5">
                                {display.config[display.id].is_device
                                    ? 'Device Config'
                                    : 'Virtual Config'}
                            </Typography>
                            {display.config[display.id].is_device && (
                                <>
                                    <Button variant="outlined" onClick={handleClick}>
                                        <NetworkCheckIcon />
                                    </Button>
                                    <Popover
                                        id={display.id}
                                        open={Boolean(anchorEl)}
                                        anchorEl={anchorEl}
                                        onClose={handleClose}
                                        anchorOrigin={{
                                            vertical: 'bottom',
                                            horizontal: 'right',
                                        }}
                                        transformOrigin={{
                                            vertical: 'top',
                                            horizontal: 'right',
                                        }}
                                        style={{
                                            marginTop: '0.25rem',
                                        }}
                                    >
                                        <div
                                            style={{
                                                padding: '1rem',
                                                fontVariant: 'all-small-caps',
                                            }}
                                        >
                                            {!pingData ? (
                                                <div
                                                    style={{
                                                        display: 'flex',
                                                        justifyContent: 'space-between',
                                                        alignItems: 'center',
                                                        flexDirection: 'column',
                                                        minWidth: '220px',
                                                        minHeight: '90px',
                                                    }}
                                                >
                                                    <Typography className={classes.title}>
                                                        pinging...
                                                    </Typography>
                                                    <CircularProgress color="primary" />
                                                </div>
                                            ) : (
                                                <>
                                                    <Grid
                                                        container
                                                        spacing={4}
                                                        style={{
                                                            width: 'calc(max(38.5vw, 480px))',
                                                            paddingLeft: '0.5rem',
                                                        }}
                                                    >
                                                        <Grid item xs={12} lg={6}>
                                                            <Divider
                                                                style={{
                                                                    marginBottom: '0.25rem',
                                                                }}
                                                            />
                                                            <div
                                                                style={{
                                                                    display: 'flex',
                                                                    alignItems: 'center',
                                                                    justifyContent: 'flex-start',
                                                                    fontSize: '1.5rem',
                                                                }}
                                                            >
                                                                <Icon
                                                                    style={{
                                                                        marginRight: '0.7rem',
                                                                    }}
                                                                >
                                                                    <Wled />
                                                                </Icon>

                                                                {wledData.name}
                                                            </div>
                                                            <Divider
                                                                style={{
                                                                    margin: '0.25rem 0 1rem 0',
                                                                }}
                                                            />
                                                            <div
                                                                style={{
                                                                    display: 'flex',
                                                                    justifyContent: 'space-between',
                                                                    minWidth: '180px',
                                                                }}
                                                            >
                                                                <Typography
                                                                    className={classes.title}
                                                                >
                                                                    MAXIMUM PING
                                                                </Typography>
                                                                <Typography>
                                                                    {pingData.max_ping
                                                                        ? pingData.max_ping.toFixed(
                                                                              2
                                                                          )
                                                                        : 0}{' '}
                                                                    ms
                                                                </Typography>
                                                            </div>
                                                            <div
                                                                style={{
                                                                    display: 'flex',
                                                                    justifyContent: 'space-between',
                                                                    minWidth: '220px',
                                                                }}
                                                            >
                                                                <Typography
                                                                    className={classes.title}
                                                                >
                                                                    AVERAGE PING
                                                                </Typography>
                                                                <Typography>
                                                                    {pingData.avg_ping
                                                                        ? pingData.avg_ping.toFixed(
                                                                              2
                                                                          )
                                                                        : 0}{' '}
                                                                    ms
                                                                </Typography>
                                                            </div>
                                                            <div
                                                                style={{
                                                                    display: 'flex',
                                                                    justifyContent: 'space-between',
                                                                    minWidth: '220px',
                                                                }}
                                                            >
                                                                <Typography
                                                                    className={classes.title}
                                                                >
                                                                    MINIMUM PING
                                                                </Typography>
                                                                <Typography>
                                                                    {pingData.min_ping
                                                                        ? pingData.min_ping.toFixed(
                                                                              2
                                                                          )
                                                                        : 0}{' '}
                                                                    ms
                                                                </Typography>
                                                            </div>
                                                            <div
                                                                style={{
                                                                    display: 'flex',
                                                                    justifyContent: 'space-between',
                                                                    minWidth: '220px',
                                                                }}
                                                            >
                                                                <Typography
                                                                    className={classes.title}
                                                                >
                                                                    PACKETS LOST
                                                                </Typography>
                                                                <Typography
                                                                    style={{
                                                                        paddingRight: '0.1rem',
                                                                    }}
                                                                >
                                                                    {pingData.packetlosspercent
                                                                        ? pingData.packetlosspercent.toFixed(
                                                                              2
                                                                          )
                                                                        : 0}
                                                                    &nbsp;%&nbsp;
                                                                </Typography>
                                                            </div>
                                                            <Divider style={{ margin: '1rem 0' }} />
                                                            <div
                                                                style={{
                                                                    display: 'flex',
                                                                    justifyContent: 'space-between',
                                                                    minWidth: '220px',
                                                                }}
                                                            >
                                                                <Typography
                                                                    className={classes.title}
                                                                >
                                                                    WiFi Signal strength
                                                                </Typography>
                                                                <Typography
                                                                    style={{
                                                                        paddingRight: '0.1rem',
                                                                    }}
                                                                >
                                                                    {wledData.wifi.signal}%
                                                                </Typography>
                                                            </div>
                                                            <div
                                                                style={{
                                                                    display: 'flex',
                                                                    justifyContent: 'space-between',
                                                                    minWidth: '220px',
                                                                }}
                                                            >
                                                                <Typography
                                                                    className={classes.title}
                                                                >
                                                                    WiFi Channel
                                                                </Typography>
                                                                <Typography
                                                                    style={{
                                                                        paddingRight: '0.1rem',
                                                                    }}
                                                                >
                                                                    {wledData.wifi.channel}
                                                                </Typography>
                                                            </div>
                                                            <div
                                                                style={{
                                                                    display: 'flex',
                                                                    justifyContent: 'space-between',
                                                                    minWidth: '220px',
                                                                }}
                                                            >
                                                                <Typography
                                                                    className={classes.title}
                                                                >
                                                                    MAC
                                                                </Typography>
                                                                <Typography
                                                                    style={{
                                                                        paddingRight: '0.1rem',
                                                                    }}
                                                                >
                                                                    {wledData.mac}
                                                                </Typography>
                                                            </div>

                                                            {wledData.leds.fps > 0 && (
                                                                <div
                                                                    style={{
                                                                        display: 'flex',
                                                                        justifyContent:
                                                                            'space-between',
                                                                        minWidth: '220px',
                                                                    }}
                                                                >
                                                                    <Typography
                                                                        className={classes.title}
                                                                    >
                                                                        Frames Per Second
                                                                    </Typography>
                                                                    <Typography
                                                                        style={{
                                                                            paddingRight: '0.1rem',
                                                                        }}
                                                                    >
                                                                        {wledData.leds.fps}
                                                                    </Typography>
                                                                </div>
                                                            )}
                                                        </Grid>
                                                        <Grid item xs={12} lg={6}>
                                                            {/* <div
                                                                style={{
                                                                    display: 'flex',
                                                                    justifyContent: 'space-between',
                                                                    minWidth: '220px',
                                                                }}
                                                            >
                                                                <Typography
                                                                    className={classes.title}
                                                                >
                                                                    NAME
                                                                </Typography>
                                                                <Typography
                                                                    style={{
                                                                        paddingRight: '0.1rem',
                                                                    }}
                                                                >
                                                                    {wledData.name}
                                                                </Typography>
                                                            </div> */}
                                                            <Divider
                                                                style={{ margin: ' 0 0 0.5rem 0' }}
                                                            />
                                                            <div
                                                                style={{
                                                                    display: 'flex',
                                                                    justifyContent: 'space-between',
                                                                    minWidth: '220px',
                                                                }}
                                                            >
                                                                <Typography
                                                                    className={classes.title}
                                                                >
                                                                    Version
                                                                </Typography>
                                                                <Typography
                                                                    style={{
                                                                        paddingRight: '0.1rem',
                                                                    }}
                                                                >
                                                                    {wledData.ver}
                                                                </Typography>
                                                            </div>
                                                            <div
                                                                style={{
                                                                    display: 'flex',
                                                                    justifyContent: 'space-between',
                                                                    minWidth: '220px',
                                                                }}
                                                            >
                                                                <Typography
                                                                    className={classes.title}
                                                                >
                                                                    Chip
                                                                </Typography>
                                                                <Typography
                                                                    style={{
                                                                        paddingRight: '0.1rem',
                                                                    }}
                                                                >
                                                                    {wledData.arch}
                                                                </Typography>
                                                            </div>
                                                            <div
                                                                style={{
                                                                    display: 'flex',
                                                                    justifyContent: 'space-between',
                                                                    minWidth: '220px',
                                                                }}
                                                            >
                                                                <Typography
                                                                    className={classes.title}
                                                                >
                                                                    LED Count
                                                                </Typography>
                                                                <Typography
                                                                    style={{
                                                                        paddingRight: '0.1rem',
                                                                    }}
                                                                >
                                                                    {wledData.leds.count}
                                                                </Typography>
                                                            </div>
                                                            <div
                                                                style={{
                                                                    display: 'flex',
                                                                    justifyContent: 'space-between',
                                                                    minWidth: '220px',
                                                                }}
                                                            >
                                                                <Typography
                                                                    className={classes.title}
                                                                >
                                                                    RGBW
                                                                </Typography>
                                                                <Typography
                                                                    style={{
                                                                        paddingRight: '0.1rem',
                                                                    }}
                                                                >
                                                                    {JSON.stringify(
                                                                        wledData.leds.rgbw
                                                                    )}
                                                                </Typography>
                                                            </div>
                                                            <div
                                                                style={{
                                                                    display: 'flex',
                                                                    justifyContent: 'space-between',
                                                                    minWidth: '220px',
                                                                }}
                                                            >
                                                                <Typography
                                                                    className={classes.title}
                                                                >
                                                                    Estimated Power
                                                                </Typography>
                                                                <Typography
                                                                    style={{
                                                                        paddingRight: '0.1rem',
                                                                    }}
                                                                >
                                                                    {wledData.leds.pwr
                                                                        .toString()
                                                                        .replace(
                                                                            /\B(?=(\d{3})+(?!\d))/g,
                                                                            ','
                                                                        )}
                                                                    mA
                                                                </Typography>
                                                            </div>
                                                            <div
                                                                style={{
                                                                    display: 'flex',
                                                                    justifyContent: 'space-between',
                                                                    minWidth: '220px',
                                                                }}
                                                            >
                                                                <Typography
                                                                    className={classes.title}
                                                                >
                                                                    Max power
                                                                </Typography>
                                                                <Typography
                                                                    style={{
                                                                        paddingRight: '0.1rem',
                                                                    }}
                                                                >
                                                                    {wledData.leds.maxpwr
                                                                        .toString()
                                                                        .replace(
                                                                            /\B(?=(\d{3})+(?!\d))/g,
                                                                            ','
                                                                        )}
                                                                    mA
                                                                </Typography>
                                                            </div>
                                                            <div
                                                                style={{
                                                                    display: 'flex',
                                                                    justifyContent: 'space-between',
                                                                    minWidth: '220px',
                                                                }}
                                                            >
                                                                <Typography
                                                                    className={classes.title}
                                                                >
                                                                    Live Mode
                                                                </Typography>
                                                                <Typography
                                                                    style={{
                                                                        paddingRight: '0.1rem',
                                                                    }}
                                                                >
                                                                    {JSON.stringify(wledData.live)}
                                                                </Typography>
                                                            </div>
                                                            <div
                                                                style={{
                                                                    display: 'flex',
                                                                    justifyContent: 'space-between',
                                                                    minWidth: '220px',
                                                                }}
                                                            >
                                                                <Typography
                                                                    className={classes.title}
                                                                >
                                                                    Live Mode Source
                                                                </Typography>
                                                                <Typography
                                                                    style={{
                                                                        paddingRight: '0.1rem',
                                                                    }}
                                                                >
                                                                    {wledData.lip}
                                                                </Typography>
                                                            </div>
                                                            <div
                                                                style={{
                                                                    display: 'flex',
                                                                    justifyContent: 'space-between',
                                                                    minWidth: '220px',
                                                                }}
                                                            >
                                                                <Typography
                                                                    className={classes.title}
                                                                >
                                                                    Live Mode Protocol
                                                                </Typography>
                                                                <Typography
                                                                    style={{
                                                                        paddingRight: '0.1rem',
                                                                    }}
                                                                >
                                                                    {wledData.lm}
                                                                </Typography>
                                                            </div>
                                                            <div
                                                                style={{
                                                                    display: 'flex',
                                                                    justifyContent: 'space-between',
                                                                    minWidth: '220px',
                                                                }}
                                                            >
                                                                <Typography
                                                                    className={classes.title}
                                                                >
                                                                    UDP Port
                                                                </Typography>
                                                                <Typography
                                                                    style={{
                                                                        paddingRight: '0.1rem',
                                                                    }}
                                                                >
                                                                    {wledData.udpport}
                                                                </Typography>
                                                            </div>
                                                            <div
                                                                style={{
                                                                    display: 'flex',
                                                                    justifyContent: 'space-between',
                                                                    minWidth: '220px',
                                                                }}
                                                            >
                                                                <Typography
                                                                    className={classes.title}
                                                                >
                                                                    Uptime
                                                                </Typography>
                                                                <Moment
                                                                    interval={1000}
                                                                    format="hh:mm:ss"
                                                                    durationFromNow
                                                                >
                                                                    {moment().add(
                                                                        wledData.uptime * -1,
                                                                        's'
                                                                    )}
                                                                </Moment>
                                                            </div>
                                                        </Grid>
                                                    </Grid>
                                                </>
                                            )}
                                        </div>
                                    </Popover>
                                </>
                            )}
                        </div>
                        <Typography className={classes.title} variant="subtitle1">
                            Total Pixels: {display.config[display.id].pixel_count}
                        </Typography>
                        <br />
                        <Typography variant="caption">
                            Active: {JSON.stringify(display.config[display.id].active)}
                            <br />
                            Type: {JSON.stringify(display.config[display.id].config.icon_name)}
                            <br />
                            Center Offset: {display.config[display.id].config.center_offset}
                            <br />
                            Crossfade: {JSON.stringify(display.config[display.id].config.crossfade)}
                            <br />
                            Max Brightness:{' '}
                            {display.config[display.id].config.max_brightness * 100 + '%'}
                            <br />
                            Preview only:{' '}
                            {JSON.stringify(display.config[display.id].config.preview_only)}
                            <br />
                        </Typography>
                        {/* {JSON.stringify(wledData.brand) === '"WLED"'
                                ?
                                <Typography className={classes.title} variant="subtitle1">
                                    <br />
                                    WLED Device Info:
                                </Typography>
                                : ''}
                                {JSON.stringify(wledData.brand) === '"WLED"'
                                ?
                                <Typography variant="caption">
                                    Name: {JSON.stringify(wledData.name)}
                                    <br />
                                    Uptime: {secondsToString (JSON.stringify(wledData.uptime))}
                                    <br />
                                    WLED Version: {JSON.stringify(wledData.ver)},
                                    Chip: {JSON.stringify(wledData.arch)}
                                    <br />
                                    LED Count: {numberWithCommas (JSON.stringify(wledData.leds.count))},
                                    RGBW? {JSON.stringify(wledData.leds.rgbw)}
                                    <br />
                                    Estimated current: {numberWithCommas (JSON.stringify(wledData.leds.pwr))} mA,
                                    Max power: {numberWithCommas (JSON.stringify(wledData.leds.maxpwr))} mA
                                    <br />
                                    Live Mode: {JSON.stringify(wledData.live)} ,
                                    Live Mode Source: {JSON.stringify(wledData.lip)}, {JSON.stringify(wledData.lm)} ,
                                    UDP Port: {JSON.stringify(wledData.udpport)}
                                    <br />
                                    WiFi Signal strength: {JSON.stringify(wledData.wifi.signal)}%,
                                    WiFi Channel: {JSON.stringify(wledData.wifi.channel)},
                                    MAC: {JSON.stringify(wledData.mac)}
                                    <br />
                                    {JSON.stringify(wledData.leds.fps) > 0
                                    ? <Typography variant="caption">
                                        Frames Per Second: {numberWithCommas (JSON.stringify(wledData.leds.fps))} fps
                                    <br />
                                    </Typography>
                                    : ''}
                                    {JSON.stringify(wledData.freeheap) > 10000
                                    ?
                                    <Typography variant="caption">
                                        RAM available: {numberWithCommas (JSON.stringify(wledData.freeheap))} - Good
                                    </Typography>
                                    : <Typography className={classes.title} variant="subtitle1">
                                        RAM available: {JSON.stringify(wledData.freeheap)} (This is Problematic, as less than 10k)
                                    </Typography>}
                                    </Typography>
                                    : ''} */}
                    </CardContent>
                </Card>
            </Grid>
            <Grid item xs={6} lg={6}>
                <Card>
                    <CardContent>
                        <Typography variant="h5">
                            {display.config[display.id].is_device
                                ? 'Device Segments'
                                : 'Virtual Segments'}
                        </Typography>
                        <Typography variant="subtitle1">
                            Segments: {display.config[display.id].segments.length}
                        </Typography>
                        <br />
                        {display.config[display.id].segments.map((s, i) => (
                            <li key={i}>{s.join(',')}</li>
                        ))}
                    </CardContent>
                </Card>
            </Grid>
        </>
    );
};

export default MoreInfo;
