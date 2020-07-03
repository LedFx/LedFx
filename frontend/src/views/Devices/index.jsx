import React from 'react';
import { connect } from 'react-redux';
import withStyles from '@material-ui/core/styles/withStyles';
import Grid from '@material-ui/core/Grid';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import Button from '@material-ui/core/Button';
import AddIcon from '@material-ui/icons/Add';

import DevicesTable from 'components/DevicesTable';
import DeviceConfigDialog from 'components/DeviceConfigDialog';
import { addDevice, deleteDevice, updateDeviceConfig, fetchDeviceList } from 'modules/devices';

const styles = theme => ({
    cardResponsive: {
        width: '100%',
        overflowX: 'auto',
    },
    button: {
        position: 'absolute',
        bottom: theme.spacing(2),
        right: theme.spacing(2),
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

    render() {
        const {
            classes,
            deviceList,
            schemas,
            addDevice,
            deleteDevice,
            updateDeviceConfig,
        } = this.props;
        const { addDialogOpened, selectedDevice } = this.state;

        return (
            <>
                <Grid container spacing={2}>
                    <Grid item xs={12} md={12}>
                        <Card>
                            <CardContent>
                                <DevicesTable
                                    items={deviceList}
                                    onDeleteDevice={deleteDevice}
                                    onEditDevice={this.handleEditDevice}
                                />
                            </CardContent>
                        </Card>
                    </Grid>
                </Grid>
                {!schemas.isLoading && (
                    <>
                        <Button
                            variant="contained"
                            color="primary"
                            aria-label="Add"
                            className={classes.button}
                            onClick={this.openAddDeviceDialog}
                        >
                            <AddIcon />
                        </Button>
                        <DeviceConfigDialog
                            open={addDialogOpened}
                            onClose={this.closeAddDeviceDialog}
                            deviceTypes={schemas.deviceTypes}
                            onAddDevice={addDevice}
                            initial={selectedDevice}
                            onUpdateDevice={updateDeviceConfig}
                        />
                    </>
                )}
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
        updateDeviceConfig,
        fetchDeviceList,
    }
)(withStyles(styles)(DevicesView));
