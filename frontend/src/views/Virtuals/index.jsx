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
import DndList from 'components/DndList';
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
    scanProgress,
    fetchDeviceList,
}) => {
    const test = {}
    // test[listItem.yz] = { led_start: 1, led_end: 3, pixels: 1 }
    const [config, setconfig] = useState(test)



    const [totalPixel, settotalPixel] = useState(0)


    const [vstrips, setvstrips] = useState([])

    const [deviceListYz, setdeviceListYz] = useState([])




    useEffect(() => {
        console.log(vstrips)
        setdeviceListYz(vstrips.map((v, i) => {
            console.log("YZ00002", deviceList, v, i)
            const output = deviceList.filter(d => d.name === v.name)[0]

            output["id"] = `${output.key}-${i}`
            if (!output["yz"]) {
                output["yz"] = `${output.key}-${i}`
            }
            output['led_start'] = 1337;
            output['led_end'] = 1337;

            // output["key"] = `${output.id}-${i}`
            // console.log("YZ", output, v, i, vstrips)
            return output
        })
        )
        // console.log("YZ2", deviceListYz, vstrips)
        if (config) {
            let newPixels = 0
            const tifOptions = Object.keys(config).map(key =>

                newPixels = newPixels + config[key].pixels
            )
            settotalPixel(newPixels)
        }
    }, [deviceList, vstrips, config])

    useEffect(() => {
        fetchDeviceList()
        // if (deviceList.length > 0) {
        //     settotalPixel(deviceList.map(d => d.config.pixel_count).reduce((a, b) => a + b))
        // }
    }, [fetchDeviceList, config])

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


                            {(deviceListYz.length > 0)
                                ? <DndList
                                    items={deviceListYz}
                                    config={config}
                                    setconfig={setconfig}
                                />
                                : (<></>)
                            }



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
