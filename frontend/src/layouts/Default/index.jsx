import React, { createRef } from 'react';
import { connect } from 'react-redux';
import PropTypes from 'prop-types';
import { Switch, Route, Redirect } from 'react-router-dom';
import withStyles from '@material-ui/core/styles/withStyles';

import { fetchSchemas } from 'modules/schemas';
import { getConfig } from 'modules/settings';
import { drawerWidth } from 'utils/style';
import viewRoutes from 'routes/views';

import Header from './Header';
import Sidebar from './Sidebar';
import Sidebar2 from './Sidebar2';

const style = theme => ({
    root: {
        overflow: 'hidden',
        display: 'flex',
        width: '100%',
        height: '100%',
    },
    content: {
        flexGrow: 1,
        backgroundColor: theme.palette.background.default,
        padding: theme.spacing(3),
        minWidth: 200,
        marginTop: '44px',
        [theme.breakpoints.up('md')]: {
            marginLeft: drawerWidth,
            marginTop: '64px',
        },
        overflowY: 'auto',
    },
    toolbar: theme.mixins.toolbar,
});

class DefaultLayout extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            mobileOpen: false,
        };

        this.root = createRef();
    }

    componentDidMount() {
        const { getConfig, fetchSchemas } = this.props;
        getConfig();
        fetchSchemas();
    }

    componentDidUpdate(prevProps) {
        if (prevProps.history.location.pathname !== prevProps.location.pathname) {
            this.root.scrollTo({ top: 0, behavior: 'smooth' });

            if (this.state.mobileOpen) {
                this.setState({ mobileOpen: false });
            }
        }
    }

    setRootRef = el => {
        this.root = el;
    };

    handleDrawerToggle = () => {
        this.setState(prevState => ({ mobileOpen: !prevState.mobileOpen }));
    };

    render() {
        const { classes, deviceDictionary, location, settings } = this.props;
        const { mobileOpen } = this.state;

        return (
            <div className={classes.root} ref={this.setRootRef}>
                <Header
                    handleDrawerToggle={this.handleDrawerToggle}
                    location={location}
                    devicesDictionary={deviceDictionary}
                />
                {parseInt(window.localStorage.getItem('BladeMod')) >= 2 ? (
                    <Sidebar2
                        handleDrawerToggle={this.handleDrawerToggle}
                        open={mobileOpen}
                        location={location}
                        devMode={settings.devMode}
                    />
                ) : (
                    <Sidebar
                        handleDrawerToggle={this.handleDrawerToggle}
                        open={mobileOpen}
                        location={location}
                        devices={settings.devices}
                        devMode={settings.devMode}
                    />
                )}

                <div className={classes.content}>
                    <Switch>
                        {viewRoutes.map(({ redirect, path, to, component: Component }, key) => {
                            if (redirect) {
                                return <Redirect from={path} to={to} key={key} />;
                            }

                            return (
                                <Route
                                    exact
                                    path={path}
                                    key={key}
                                    render={routeProps => <Component {...routeProps} />}
                                />
                            );
                        })}
                    </Switch>
                </div>
            </div>
        );
    }
}

DefaultLayout.propTypes = {
    classes: PropTypes.object.isRequired,
    deviceDictionary: PropTypes.object.isRequired,
    settings: PropTypes.object.isRequired,
    schemas: PropTypes.object.isRequired,
};

export default connect(
    state => ({
        deviceDictionary: state.devices.dictionary,
        schemas: state.schemas,
        settings: state.settings,
    }),
    {
        fetchSchemas,
        getConfig,
    }
)(withStyles(style)(DefaultLayout));
