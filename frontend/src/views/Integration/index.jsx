import React from 'react';
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

import DevicesTable from 'components/InegrationComponents';
import DeviceConfigDialog from 'components/DeviceConfigDialog';
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

class IntegrationView extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            addDialogOpened: false,
            selectedDevice: {},
            searchDevicesLoading: false,
        };
    }
    componentDidMount() {
        const { fetchDeviceList } = this.props;
        fetchDeviceList();
    }

    openAddDeviceDialog = () => {
        this.setState({ selectedDevice: {}, addDialogOpened: true });
    };

    closeAddDeviceDialog = () => {
        this.setState({ selectedDevice: {}, addDialogOpened: false });
    };

    handleEditDevice = device => {
        this.setState({ selectedDevice: device, addDialogOpened: true });
    };

    handleFindDevices = () => {
        const { findWLEDDevices } = this.props;
        this.setState({ searchDevicesLoading: true });
        new Promise((resolve, reject) => {
            findWLEDDevices({ resolve, reject });
        }).then(() => {
            this.setState({ searchDevicesLoading: false });
        });
    };

    render() {
        const {
            classes,
            deviceList,
            schemas,
            addDevice,
            deleteDevice,
            updateDeviceConfig,
            scanProgress,
        } = this.props;
        const { addDialogOpened, selectedDevice } = this.state;

        return (
            <>
                <Grid container spacing={2}>
                    <Grid item xs={12} md={12}>
                        <Card>
                            <CardContent>
                                <Grid container direction="row" spacing={1} justify="space-between">
                                    <Grid item xs="auto">
                                        <Typography variant="h5">Integrations</Typography>
                                        <Typography variant="body1" color="textSecondary">
                                            Manage integrations
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
                                                    <Button
                                                        variant="contained"
                                                        color="primary"
                                                        aria-label="Add"
                                                        className={classes.button}
                                                        onClick={this.openAddDeviceDialog}
                                                        endIcon={<AddCircleIcon />}
                                                    >
                                                        Add Integration
                                                    </Button>
                                                    <DeviceConfigDialog
                                                        open={addDialogOpened}
                                                        onClose={this.closeAddDeviceDialog}
                                                        deviceTypes={schemas.deviceTypes}
                                                        onAddDevice={addDevice}
                                                        initial={selectedDevice}
                                                        onUpdateDevice={updateDeviceConfig}
                                                    />
                                                </Box>
                                            </Grid>
                                        </>
                                    )}
                                </Grid>

                                <DevicesTable
                                    items={deviceList}
                                    onDeleteDevice={deleteDevice}
                                    onEditDevice={this.handleEditDevice}
                                />


                            </CardContent>
                        </Card>
                    </Grid>
                </Grid>
            </>
        );
    }
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
)(withStyles(styles)(IntegrationView));
