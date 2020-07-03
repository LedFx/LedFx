import React from 'react';
import { connect } from 'react-redux';
import withStyles from '@material-ui/core/styles/withStyles';
import Grid from '@material-ui/core/Grid';
import Card from '@material-ui/core/Card';
import Typography from '@material-ui/core/Typography';
import CardContent from '@material-ui/core/CardContent';
import Button from '@material-ui/core/Button';
import AddCircleIcon from '@material-ui/icons/AddCircle';

import DevicesTable from 'components/DevicesTable';
import DeviceConfigDialog from 'components/DeviceConfigDialog';
import { addDevice, deleteDevice, updateDeviceConfig } from 'modules/devices';

const styles = theme => ({
    cardResponsive: {
        width: '100%',
        overflowX: 'auto',
    },
    button: {
        size: "large",
        margin: theme.spacing(1),
    },
    dialogButton: {
        float: 'right',
    },
});

class DevicesView extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            addDialogOpened: false,
            selectedDevice: {},
        };
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

    render() {
        const { classes, deviceList, schemas, addDevice, deleteDevice, updateDeviceConfig } = this.props;
        const { addDialogOpened, selectedDevice } = this.state;

        return (
            <>
                <Grid container spacing={2}>
                    <Grid item xs={12} md={12}>
                        <Card>
                            <CardContent>
                                <Grid container direction="row" spacing={1} justify="space-between">
                                    <Grid item xs="auto">
                                        <Typography variant="h5">
                                            Devices
                                        </Typography>
                                        <Typography variant="body1" color="textSecondary">
                                            Manage devices connected to LedFx
                                        </Typography>
                                    </Grid>
                                    {!schemas.isLoading && (
                                        <>
                                            <Grid item
                                                display='flex'
                                                justifyContent='flex-end' >
                                                <Button
                                                    variant="contained"
                                                    color="primary"
                                                    aria-label="Add"
                                                    className={classes.button}
                                                    onClick={this.openAddDeviceDialog}
                                                    endIcon={<AddCircleIcon />}
                                                >
                                                    Add Device
                                                </Button>
                                                <DeviceConfigDialog
                                                    open={addDialogOpened}
                                                    onClose={this.closeAddDeviceDialog}
                                                    deviceTypes={schemas.deviceTypes}
                                                    onAddDevice={addDevice}
                                                    initial={selectedDevice}
                                                    onUpdateDevice={updateDeviceConfig}
                                                />
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
    }),
    {
        addDevice,
        deleteDevice,
        updateDeviceConfig
    }
)(withStyles(styles)(DevicesView));
