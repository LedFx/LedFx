import React from 'react';
import { connect } from 'react-redux';
import { fetchDeviceList, fetchSchemasIfNeeded } from '../../actions';
import PropTypes from 'prop-types';
import { Switch, Route, Redirect } from 'react-router-dom';
import { MuiThemeProvider, createMuiTheme } from '@material-ui/core/styles';
import cyan from '@material-ui/core/colors/cyan';
import green from '@material-ui/core/colors/green';
import CssBaseline from '@material-ui/core/CssBaseline';
import withStyles from '@material-ui/core/styles/withStyles';

import Header from '../../components/Header/Header';
import Sidebar from '../../components/Sidebar/Sidebar';
import viewRoutes from '../../routes/views';
import dashboardStyle from './style';

const defaultTheme = createMuiTheme({
    palette: {
        primary: cyan,
        secondary: green,
    },
    overrides: {
        MuiFormControl: {
            root: {
                margin: 8,
                minWidth: 225,
                flex: '1 0 30%',
            },
        },
    },
});

class DefaultLayout extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            mobileOpen: false,
            theme: defaultTheme,
        };
    }

    componentDidUpdate(e) {
        if (e.history.location.pathname !== e.location.pathname) {
            this.refs.root.scrollTop = 0;
            if (this.state.mobileOpen) {
                this.setState({ mobileOpen: false });
            }
        }
    }

    componentDidMount() {
        this.props.dispatch(fetchDeviceList());
        this.props.dispatch(fetchSchemasIfNeeded());
    }

    render() {
        const { classes, rest } = this.props;

        var handleDrawerToggle = () => {
            this.setState(prevState => ({ mobileOpen: !prevState.mobileOpen }));
        };

        return (
            <div className={classes.root} ref="root">
                <CssBaseline />
                <MuiThemeProvider theme={this.state.theme}>
                    <Header
                        handleDrawerToggle={handleDrawerToggle}
                        location={this.props.location}
                    />
                    <Sidebar
                        handleDrawerToggle={handleDrawerToggle}
                        open={this.state.mobileOpen}
                        location={this.props.location}
                    />

                    <div className={classes.content}>
                        <div className={classes.toolbar} />
                        <Switch>
                            {viewRoutes.map((prop, key) => {
                                if (prop.redirect) {
                                    return <Redirect from={prop.path} to={prop.to} key={key} />;
                                }
                                return (
                                    <Route
                                        exact
                                        path={prop.path}
                                        component={prop.component}
                                        key={key}
                                    />
                                );
                            })}
                        </Switch>
                    </div>
                </MuiThemeProvider>
            </div>
        );
    }
}

DefaultLayout.propTypes = {
    classes: PropTypes.object.isRequired,
    devicesById: PropTypes.object.isRequired,
};

function mapStateToProps(state) {
    const { devicesById, schemas } = state;

    return {
        devicesById,
        schemas,
    };
}

export default connect(mapStateToProps)(withStyles(dashboardStyle)(DefaultLayout));
