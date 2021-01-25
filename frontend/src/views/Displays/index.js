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
import DisplayConfigDialog from 'components/DeviceConfigDialog';
import {
    addDisplay,
    deleteDisplay,
    updateDisplayConfig,
    fetchDisplayList,
    findWLEDDisplays,
} from 'modules/displays';

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

class DisplaysView extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            addDialogOpened: false,
            selectedDisplay: {},
            searchDisplaysLoading: false,
        };
    }
    componentDidMount() {
        const { fetchDisplayList } = this.props;
        fetchDisplayList();
    }

    openAddDisplayDialog = () => {
        this.setState({ selectedDisplay: {}, addDialogOpened: true });
    };

    closeAddDisplayDialog = () => {
        this.setState({ selectedDisplay: {}, addDialogOpened: false });
    };

    handleEditDisplay = device => {
        this.setState({ selectedDisplay: device, addDialogOpened: true });
    };

    handleFindDisplays = () => {
        const { findWLEDDisplays } = this.props;
        this.setState({ searchDisplaysLoading: true });
        new Promise((resolve, reject) => {
            findWLEDDisplays({ resolve, reject });
        }).then(() => {
            this.setState({ searchDisplaysLoading: false });
        });
    };

    render() {
        const {
            classes,
            deviceList,
            displayList,
            schemas,
            addDisplay,
            deleteDisplay,
            updateDisplayConfig,
            scanProgress,
        } = this.props;
        const { addDialogOpened, selectedDisplay } = this.state;
        const helpText = `Ensure WLED Displays are on and connected to your WiFi.\n
                          If not detected, check WLED device mDNS setting. Go to:\n
                          WLED device ip > Config > WiFi Setup > mDNS Address \n`;

        return (
            <>
                <Grid container spacing={2}>
                    <Grid item xs={12} md={12}>
                        <Card>
                            <CardContent>
                                <Grid container direction="row" spacing={1} justify="space-between">
                                    <Grid item xs="auto">
                                        <Typography variant="h5">Displays</Typography>
                                        <Typography variant="body1" color="textSecondary">
                                            Manage displays connected to LedFx
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
                                                    <Tooltip title={helpText} interactive arrow>
                                                        <Button
                                                            variant="contained"
                                                            color="primary"
                                                            aria-label="Scan"
                                                            disabled={
                                                                this.state.searchDisplaysLoading
                                                            }
                                                            className={classes.button}
                                                            onClick={this.handleFindDisplays}
                                                            endIcon={<WifiTetheringIcon />}
                                                        >
                                                            Find WLED Displays
                                                        </Button>
                                                    </Tooltip>
                                                    <Button
                                                        variant="contained"
                                                        color="primary"
                                                        aria-label="Add"
                                                        className={classes.button}
                                                        onClick={this.openAddDisplayDialog}
                                                        endIcon={<AddCircleIcon />}
                                                    >
                                                        Add Display
                                                    </Button>
                                                    <DisplayConfigDialog
                                                        open={addDialogOpened}
                                                        onClose={this.closeAddDisplayDialog}
                                                        deviceTypes={schemas.deviceTypes}
                                                        onAddDisplay={addDisplay}
                                                        initial={selectedDisplay}
                                                        onUpdateDisplay={updateDisplayConfig}
                                                    />
                                                </Box>
                                            </Grid>
                                        </>
                                    )}
                                </Grid>

                                <DisplaysTable
                                    items={displayList}
                                    onDeleteDisplay={deleteDisplay}
                                    onEditDisplay={this.handleEditDisplay}
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
        displayList: state.displays.list || [],
        schemas: state.schemas,
        scanProgress: state.devices.scanProgress,
    }),
    {
        addDisplay,
        deleteDisplay,
        updateDisplayConfig,
        fetchDisplayList,
        findWLEDDisplays,
    }
)(withStyles(styles)(DisplaysView));
