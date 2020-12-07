import React, { useEffect, useState } from 'react';
import { connect } from 'react-redux';
import withStyles from '@material-ui/core/styles/withStyles';
import Grid from '@material-ui/core/Grid';
import Card from '@material-ui/core/Card';
import Box from '@material-ui/core/Box';
import Typography from '@material-ui/core/Typography';
import CardContent from '@material-ui/core/CardContent';
import Button from '@material-ui/core/Button';
import AddCircleIcon from '@material-ui/icons/AddCircle';
import CircularProgress from '@material-ui/core/CircularProgress';
import AddVirtualDialog from 'components/AddVirtualDialog'
import DevicesTableyz from 'components/DevicesTable/indexyz';
import {
    addDevice,
    deleteDevice,
    updateDeviceConfig,
    fetchDeviceList,
    findWLEDDevices,
} from 'modules/devices';

const styles = theme => ({
    cardResponsive: {
        width: '100%',
        overflowX: 'auto',
    },
    button: {
        size: 'large',
        margin: theme.spacing(1),
    },
    dialogButton: {
        float: 'right',
    },
});

const VirtualsView = ({
    classes,
    deviceList,
    schemas,
    deleteDevice,
    scanProgress,
    fetchDeviceList,
}) => {
    // constructor(props) {
    //     super(props);
    //     this.state = {
    //         addDialogOpened: false,
    //         selectedDevice: {},
    //         searchDevicesLoading: false,
    //     };
    // }


    // const openAddDeviceDialog = () => {
    //     this.setState({ selectedDevice: {}, addDialogOpened: true });
    // };

    // const closeAddDeviceDialog = () => {
    //     this.setState({ selectedDevice: {}, addDialogOpened: false });
    // };

    // const handleEditDevice = device => {
    //     this.setState({ selectedDevice: device, addDialogOpened: true });
    // };





    // const { addDialogOpened, selectedDevice } = this.state;
    useEffect(() => {
        fetchDeviceList()
    }, [fetchDeviceList])

    let totalPixel = 0
    if (deviceList.length > 0) {
        totalPixel = deviceList.map(d => d.config.pixel_count).reduce((a, b) => a + b)
    }

    // const vstrip = {
    //     name: "V-Strip-1",
    //     items: []
    // }
    const [vstrips, setvstrips] = useState([])
    let deviceListYz = vstrips.map(v => deviceList.filter(d => d.name === v.name)[0])



    useEffect(() => {
        deviceListYz = vstrips.map(v => deviceList.filter(d => d.name === v.name)[0])

    }, [deviceList])


    return (
        <>
            <Grid container spacing={2}>
                <Grid item xs={12} md={12}>
                    <Card>
                        <CardContent>
                            <Grid container direction="row" spacing={1} justify="space-between">
                                <Grid item xs="auto">
                                    <Typography variant="h5">V-Strip-1</Typography>
                                </Grid>
                                <Grid item xs="auto">
                                    <Typography variant="body1" color="textSecondary">
                                        Total Pixels: {totalPixel}
                                    </Typography>
                                </Grid>
                                {!schemas.isLoading && (
                                    <>
                                        <Grid item>
                                            <Box
                                                display="flex"
                                                flexDirection="row"
                                                alignItems="center"
                                                justifyContent="center"
                                            >
                                                <CircularProgress
                                                    variant="determinate"
                                                    value={scanProgress * 10}
                                                    size={35}
                                                />
                                                <AddVirtualDialog deviceList={deviceList} setvstrips={setvstrips} vstrips={vstrips} />
                                            </Box>

                                        </Grid>
                                    </>
                                )}
                            </Grid>

                            {/* {(deviceList.length > 0) && <DevicesTableyz
                                items={deviceList}
                                classes={classes}
                                onDeleteDevice={deleteDevice}
                            // onEditDevice={handleEditDevice}
                            />} */}
                            {(deviceListYz.length > 0) ? <DevicesTableyz
                                items={deviceListYz}
                                classes={classes}
                                onDeleteDevice={deleteDevice}
                            // onEditDevice={handleEditDevice}
                            /> : (<></>)}

                            {/* {(deviceListYz.length > 0) ?
                                deviceListYz.map((d => JSON.stringify(d))) : (<></>)} */}


                        </CardContent>
                    </Card>
                    <Button
                        variant="contained"
                        color="primary"
                        aria-label="Add"
                        className={classes.button}
                        // onClick={openAddDeviceDialog}
                        endIcon={<AddCircleIcon />}
                    >
                        Add New Virtual
                        </Button>
                </Grid>
            </Grid>
        </>
    );

}

export default connect(
    state => ({
        deviceList: state.devices.list,
        schemas: state.schemas,
        scanProgress: state.devices.scanProgress,
    }),
    {
        addDevice,
        deleteDevice,
        updateDeviceConfig,
        fetchDeviceList,
        findWLEDDevices,
    }
)(withStyles(styles)(VirtualsView));
