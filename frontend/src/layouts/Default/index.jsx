import React, { createRef } from 'react';
import { connect } from 'react-redux';
import PropTypes from 'prop-types';
import { Switch, Route, Redirect } from 'react-router-dom';
import withStyles from '@material-ui/core/styles/withStyles';

import { fetchDeviceList } from 'modules/devices';
import { fetchSchemas } from 'modules/schemas';
import { drawerWidth } from 'utils/style';
import Header from 'components/Header';
import Sidebar from 'components/Sidebar';
import viewRoutes from 'routes/views';

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
        [theme.breakpoints.up('md')]: {
            marginLeft: drawerWidth,
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
        this.props.fetchDeviceList();
        this.props.fetchSchemas();
    }

    componentDidUpdate(nextProps) {
        if (nextProps.history.location.pathname !== nextProps.location.pathname) {
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
        const { classes, deviceDictionary } = this.props;

        return (
            <div className={classes.root} ref={this.setRootRef}>
                <Header
                    handleDrawerToggle={this.handleDrawerToggle}
                    location={this.props.location}
                    devicesDictionary={deviceDictionary}
                />
                <Sidebar
                    handleDrawerToggle={this.handleDrawerToggle}
                    open={this.state.mobileOpen}
                    location={this.props.location}
                    devicesDictionary={deviceDictionary}
                />

                <div className={classes.content}>
                    <div className={classes.toolbar} />
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
};

export default connect(
    state => ({
        deviceDictionary: state.devices.dictionary,
        schemas: state.schemas,
    }),
    {
        fetchDeviceList,
        fetchSchemas,
    }
)(withStyles(style)(DefaultLayout));
