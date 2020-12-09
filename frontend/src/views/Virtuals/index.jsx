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

    const [config, setconfig] = useState({})
    const [totalPixel, settotalPixel] = useState(0)
    const [vstrips, setvstrips] = useState([])
    const [deviceListYz, setdeviceListYz] = useState([])


    useEffect(() => {
        setdeviceListYz(vstrips.map((v, i) => {
            const output = { ...deviceList.find(d => d.name === v.name) }
            output["id"] = '' + output.key + '-yz-' + i
            output["yz"] = output["id"]
            output["key"] = output["id"]
            return output
        })
        )

        if (config) {
            let newPixels = 0
            const calcPixels = Object.keys(config).map(key => // eslint-disable-no-unused-vars
                newPixels = newPixels + (config[key].led_end - config[key].led_start)
            )
            settotalPixel(newPixels)
            console.log(calcPixels, config)
        }
    }, [deviceList, vstrips, config])

    useEffect(() => {
        fetchDeviceList()
    }, [fetchDeviceList])

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
                                {totalPixel > 0
                                    ? (
                                        <Grid item xs="auto">
                                            <Typography variant="body1" color="textSecondary">
                                                Total Pixels: {totalPixel}
                                            </Typography>
                                        </Grid>
                                    )
                                    : (<></>)}

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
                                    setdeviceListYz={setdeviceListYz}
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
