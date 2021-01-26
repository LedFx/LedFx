import React from 'react';
import { connect } from 'react-redux';
import withStyles from '@material-ui/core/styles/withStyles';
import Grid from '@material-ui/core/Grid';
import Card from '@material-ui/core/Card';
// import Box from '@material-ui/core/Box';
import Typography from '@material-ui/core/Typography';
import CardContent from '@material-ui/core/CardContent';
// import Button from '@material-ui/core/Button';

import DisplaysTable from 'components/DisplaysTable';
// import DisplayConfigDialog from 'components/DeviceConfigDialog';
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

    handleEditDisplay = display => {
        this.setState({ selectedDisplay: display, addDialogOpened: true });
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
            displayList,
            // schemas,
            // addDisplay,
            deleteDisplay,
            // updateDisplayConfig,
        } = this.props;
        // const { addDialogOpened, selectedDisplay } = this.state;

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
        displayList: state.displays.list || [],
        schemas: state.schemas,
    }),
    {
        addDisplay,
        deleteDisplay,
        updateDisplayConfig,
        fetchDisplayList,
        findWLEDDisplays,
    }
)(withStyles(styles)(DisplaysView));
