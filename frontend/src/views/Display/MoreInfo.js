import React from 'react';
import Grid from '@material-ui/core/Grid';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import Typography from '@material-ui/core/Typography';
import { Button, CircularProgress, Popover } from '@material-ui/core';
import NetworkCheckIcon from '@material-ui/icons/NetworkCheck';
import { makeStyles } from '@material-ui/core/styles';
import * as displayProxies from 'proxies/display';
import { getDevice } from 'proxies/device';

const useStyles = makeStyles(theme => ({
    title: {
        color: theme.palette.text.secondary,
    },
}));

const MoreInfo =  ({ display }) => {
    console.log(display);
    const classes = useStyles();
    const [anchorEl, setAnchorEl] = React.useState();
    const [pingData, setPingData] = React.useState();
    const [wled, setWLEDData] = React.useState({});

    React.useEffect(() => {
        console.log("component mounted")
        getdeviceIP()
        .then(res => setWLEDData(res))
    }, []);

    const handleClick = event => {
        console.log('YZ1', pingData);
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
            if (response.statusText === 'OK') {
                setPingData(response.data);
            }
        } catch (error) {
            console.log('Error deleting display', error.message);
        }
    };
    console.log('YZ0', pingData);

    const getdeviceIP = async () => {
        try {
            const response = await getDevice(display.id);
            if (response.config.type === 'wled') {
                const ip = response.config.ip_address
                const res = await fetch(`http://${ip}/json/info`);
                let wledResponse = await res.json();
                console.log('Testing123',wledResponse);
                return wledResponse;
            }
        } catch (error) {
            console.log('Error getting WLED info from device', error.message);
        }
    };
    let wledData = {brand:'Not getting here2'};
    if (display.config[display.id].config.icon_name === "wled" && display.config[display.id].active === true) {
        // wledData has the value stored but since its an object it can not be rendered as React child
        // Either fetch from object what we need to display
        // or convert object into array and render all components
        //or JSON stringify the rendered value : done
        if(Object.keys(wled).length>0){
            console.log("jyotir",wled)
            wledData = wled;
        }    
    }
        


    
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
                                        style={{ marginTop: '0.25rem' }}
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
                                                    <div
                                                        style={{
                                                            display: 'flex',
                                                            justifyContent: 'space-between',
                                                            minWidth: '180px',
                                                        }}
                                                    >
                                                        <Typography className={classes.title}>
                                                            MAXIMUM PING
                                                        </Typography>
                                                        <Typography>
                                                            {pingData.max_ping
                                                                ? pingData.max_ping.toFixed(2)
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
                                                        <Typography className={classes.title}>
                                                            AVERAGE PING
                                                        </Typography>
                                                        <Typography>
                                                            {pingData.avg_ping
                                                                ? pingData.avg_ping.toFixed(2)
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
                                                        <Typography className={classes.title}>
                                                            MINIMUM PING
                                                        </Typography>
                                                        <Typography>
                                                            {pingData.min_ping
                                                                ? pingData.min_ping.toFixed(2)
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
                                                        <Typography className={classes.title}>
                                                            PACKETS LOST
                                                        </Typography>
                                                        <Typography
                                                            style={{ paddingRight: '0.1rem' }}
                                                        >
                                                            {pingData.packetlosspercent
                                                                ? pingData.packetlosspercent.toFixed(
                                                                      2
                                                                  )
                                                                : 0}
                                                            &nbsp;%&nbsp;
                                                        </Typography>
                                                    </div>
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
                                Type:{' '}
                                {JSON.stringify(display.config[display.id].config.icon_name)}
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
                                {JSON.stringify(wledData.brand)}
                                </Typography>
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
