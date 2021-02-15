import React from 'react';
import { connect } from 'react-redux';
import withStyles from '@material-ui/core/styles/withStyles';
import Grid from '@material-ui/core/Grid';
import Card from '@material-ui/core/Card';
import Box from '@material-ui/core/Box';
import Typography from '@material-ui/core/Typography';
import CardContent from '@material-ui/core/CardContent';
import Button from '@material-ui/core/Button';
import Tooltip from '@material-ui/core/Tooltip';
import AddCircleIcon from '@material-ui/icons/AddCircle';
import WifiTetheringIcon from '@material-ui/icons/WifiTethering';
import CircularProgress from '@material-ui/core/CircularProgress';
import DisplaysTable from 'components/DisplaysTable';
import DeviceConfigDialog from 'components/DeviceConfigDialog';
import DisplayConfigDialog from 'components/DisplayConfigDialog';
import { addDevice, updateDeviceConfig, fetchDeviceList, findWLEDDevices } from 'modules/devices';
import { deleteDisplay, fetchDisplayList, addDisplay } from 'modules/displays';
import { updateDisplay } from 'proxies/display';
import DisplayCards from 'components/DisplaysTable/DisplayCards';
import ViewListIcon from '@material-ui/icons/ViewList';
import ViewModuleIcon from '@material-ui/icons/ViewModule';
import ToggleButton from '@material-ui/lab/ToggleButton';
import ToggleButtonGroup from '@material-ui/lab/ToggleButtonGroup';
import TableChartIcon from '@material-ui/icons/TableChart';
// import Fab from '@material-ui/core/Fab';
// import AddIcon from '@material-ui/icons/Add';
// import Menu from '@material-ui/core/Menu';
// import MenuItem from '@material-ui/core/MenuItem';
// import ListItemIcon from '@material-ui/core/ListItemIcon';
// import ListItemText from '@material-ui/core/ListItemText';

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
    buttonWrapper: {
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        '@media (max-width: 540px)': {
            flexDirection: 'column',
            alignItems: 'stretch',
        },
    },
    topBar: {
        '@media (max-width: 540px)': {
            flexDirection: 'column',
            alignItems: 'stretch',
        },
    },
    // fab: {
    //     position: 'absolute',
    //     bottom: theme.spacing(2),
    //     right: theme.spacing(2),
    // },
});

class DevicesView extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            addDialogOpened: false,
            addDisplayOpened: false,
            selectedDevice: {},
            selectedDisplay: {},
            searchDevicesLoading: false,
            view: 'cardsPortrait',
        };
    }
    handleChange = (event, nextView) => {
        this.setState({ view: nextView });
    };

    componentDidMount() {
        const { fetchDeviceList, fetchDisplayList } = this.props;
        fetchDeviceList();

        fetchDisplayList();
    }

    openAddDeviceDialog = () => {
        this.setState({ selectedDevice: {}, addDialogOpened: true });
    };
    openAddDisplayDialog = () => {
        this.setState({ selectedDisplay: {}, addDisplayOpened: true });
    };

    closeAddDeviceDialog = () => {
        this.setState({ selectedDevice: {}, addDialogOpened: false });
    };
    closeAddDisplayDialog = () => {
        this.setState({ selectedDisplay: {}, addDisplayOpened: false });
    };

    handleEditDevice = device => {
        this.setState({ selectedDevice: device, addDialogOpened: true });
    };
    handleEditDisplay = display => {
        this.setState({ selectedDisplay: display, addDisplayOpened: true });
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
    // openMenu = () => {
    //     alert('menu');
    // };
    render() {
        const {
            classes,
            deviceList,
            displayList,
            deleteDisplay,
            schemas,
            addDevice,
            addDisplay,
            updateDeviceConfig,
            scanProgress,
        } = this.props;
        const { addDialogOpened, selectedDevice } = this.state;
        const { addDisplayOpened, selectedDisplay } = this.state;

        return (
            <>
                <Grid container spacing={2}>
                    <Grid item xs={12}>
                        <Card>
                            <CardContent>
                                <Grid
                                    className={classes.topBar}
                                    container
                                    direction="row"
                                    spacing={1}
                                    justify="space-between"
                                >
                                    <Grid item xs="auto">
                                        <Typography variant="h5">{/* Devices */}</Typography>
                                        <Typography
                                            variant="body1"
                                            color="textSecondary"
                                        ></Typography>
                                    </Grid>
                                    {!schemas.isLoading && (
                                        <>
                                            <Grid item>
                                                <Box className={classes.buttonWrapper}>
                                                    {this.state.searchDevicesLoading && (
                                                        <CircularProgress
                                                            variant="determinate"
                                                            value={scanProgress * 10}
                                                            size={35}
                                                        />
                                                    )}

                                                    <Tooltip
                                                        title={
                                                            <ul style={{ padding: '0.5rem' }}>
                                                                <li>
                                                                    Ensure WLED Devices are on and
                                                                    connected to your WiFi.
                                                                </li>
                                                                <li>
                                                                    If not detected, check WLED
                                                                    device mDNS setting. Go to:
                                                                </li>
                                                                <li>
                                                                    WLED device ip - Config - WiFi
                                                                    Setup - mDNS Address{' '}
                                                                </li>
                                                            </ul>
                                                        }
                                                        interactive
                                                        arrow
                                                    >
                                                        <Button
                                                            variant={"contained"}
                                                            color={"primary"}
                                                            aria-label="Scan"
                                                            disabled={
                                                                this.state.searchDevicesLoading
                                                            }
                                                            className={classes.button}
                                                            onClick={this.handleFindDevices}
                                                            endIcon={<WifiTetheringIcon />}
                                                        >
                                                            Find WLEDs
                                                        </Button>
                                                    </Tooltip>
                                                    <Tooltip
                                                        title={
                                                            <>
                                                                <h2>Add Virtual Device</h2>
                                                                <ul style={{ padding: '0.5rem' }}>
                                                                    <li>
                                                                        A virtual device lets you
                                                                        control the mapping of an effect
                                                                        onto devices. You can:
                                                                </li>
                                                                    <li>
                                                                        Split a device to show multiple
                                                                        effects
                                                                </li>
                                                                    <li>
                                                                        Combine devices to show a single
                                                                        effect
                                                                </li>
                                                                    <li>
                                                                        Or any combination of the two!
                                                                </li>
                                                                </ul>
                                                            </>
                                                        }
                                                        interactive
                                                        arrow
                                                    >
                                                        <Button
                                                            variant={"contained"}
                                                            color={"primary"}
                                                            aria-label="Scan"
                                                            className={classes.button}
                                                            onClick={this.openAddDisplayDialog}
                                                            endIcon={<AddCircleIcon />}
                                                        >
                                                            Virtual
                                                        </Button>
                                                    </Tooltip>
                                                    <Button
                                                        variant={"contained"}
                                                        color={"primary"}
                                                        aria-label="Add"
                                                        className={classes.button}
                                                        onClick={this.openAddDeviceDialog}
                                                        endIcon={<AddCircleIcon />}
                                                    >
                                                        Device
                                                    </Button>

                                                    <ToggleButtonGroup
                                                        value={this.state.view}
                                                        exclusive
                                                        onChange={this.handleChange}
                                                    >
                                                        <ToggleButton
                                                            value="list"
                                                            aria-label="list"
                                                        >
                                                            <TableChartIcon />
                                                        </ToggleButton>
                                                        <ToggleButton
                                                            value="cards"
                                                            aria-label="cards"
                                                        >
                                                            <ViewListIcon />
                                                        </ToggleButton>
                                                        <ToggleButton
                                                            value="cardsPortrait"
                                                            aria-label="cardsPortrait"
                                                        >
                                                            <ViewModuleIcon />
                                                        </ToggleButton>
                                                    </ToggleButtonGroup>

                                                    <DeviceConfigDialog
                                                        open={addDialogOpened}
                                                        onClose={this.closeAddDeviceDialog}
                                                        deviceTypes={schemas.deviceTypes}
                                                        onAddDevice={addDevice}
                                                        initial={selectedDevice}
                                                        onUpdateDevice={updateDeviceConfig}
                                                    />
                                                    <DisplayConfigDialog
                                                        open={addDisplayOpened}
                                                        displays={schemas.displays}
                                                        onClose={this.closeAddDisplayDialog}
                                                        onAddDisplay={addDisplay}
                                                        initial={selectedDisplay}
                                                        onUpdateDisplay={updateDisplay}
                                                    />
                                                </Box>
                                            </Grid>
                                        </>
                                    )}
                                </Grid>
                                {this.state.view === 'list' && (
                                    <DisplaysTable
                                        items={displayList}
                                        deviceList={deviceList}
                                        onEditDevice={this.handleEditDevice}
                                        onDeleteDisplay={deleteDisplay}
                                        onEditDisplay={this.handleEditDisplay}
                                    />
                                )}
                            </CardContent>
                        </Card>
                    </Grid>
                    {this.state.view === 'cards' && (
                        <Grid item xs={12}>
                            <DisplayCards
                                items={displayList}
                                deviceList={deviceList}
                                onEditDevice={this.handleEditDevice}
                                onDeleteDisplay={deleteDisplay}
                                onEditDisplay={this.handleEditDisplay}
                                view={'cards'}
                            />
                        </Grid>
                    )}
                    {this.state.view === 'cardsPortrait' && (
                        <Grid item xs={12}>
                            <DisplayCards
                                items={displayList}
                                deviceList={deviceList}
                                onEditDevice={this.handleEditDevice}
                                onDeleteDisplay={deleteDisplay}
                                onEditDisplay={this.handleEditDisplay}
                                view={'cardsPortrait'}
                            />
                        </Grid>
                    )}
                </Grid>
                {/* <Fab
                    color="primary"
                    aria-label="add"
                    className={classes.fab}
                    onClick={this.openMenu}
                >
                    <AddIcon />
                </Fab>
                <Menu>
                    <MenuItem>
                        <ListItemIcon>
                            <AddIcon fontSize="small" />
                        </ListItemIcon>
                        <ListItemText primary="Sent mail" />
                    </MenuItem>
                    <MenuItem>
                        <ListItemIcon>
                            <AddIcon fontSize="small" />
                        </ListItemIcon>
                        <ListItemText primary="Drafts" />
                    </MenuItem>
                    <MenuItem>
                        <ListItemIcon>
                            <AddIcon fontSize="small" />
                        </ListItemIcon>
                        <ListItemText primary="Inbox" />
                    </MenuItem>
                </Menu> */}
            </>
        );
    }
}

export default connect(
    state => ({
        deviceList: state.devices.list,
        displayList: state.displays.list || [],
        schemas: state.schemas,
        scanProgress: state.devices.scanProgress,
    }),
    {
        addDevice,
        addDisplay,
        deleteDisplay,
        updateDeviceConfig,
        fetchDeviceList,
        findWLEDDevices,
        fetchDisplayList,
    }
)(withStyles(styles)(DevicesView));
