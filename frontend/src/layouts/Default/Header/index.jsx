import React from 'react';
import PropTypes from 'prop-types';
import withStyles from '@material-ui/core/styles/withStyles';
import AppBar from '@material-ui/core/AppBar';
import Toolbar from '@material-ui/core/Toolbar';
import IconButton from '@material-ui/core/IconButton';
import Hidden from '@material-ui/core/Hidden';
import Typography from '@material-ui/core/Typography';
import Menu from '@material-ui/icons/Menu';

import viewRoutes from 'routes/views.jsx';
import { drawerWidth } from 'utils/style';

const styles = theme => ({
    appBar: {
        backgroundColor: 'transparent',
        boxShadow: 'none',
        position: 'absolute',
        marginLeft: drawerWidth,
        [theme.breakpoints.up('md')]: {
            width: `calc(100% - ${drawerWidth}px)`,
        },
    },
    flex: {
        flex: 1,
        fontSize: 18,
        fontWeight: 300,
    },
});

class Header extends React.Component {
    getPageName() {
        const { location, devicesDictionary } = this.props;
        const { pathname } = location;
        let name = viewRoutes.find((prop, key) => prop.path === pathname)?.navbarName;

        if (!name) {
            if (pathname.startsWith('/devices/')) {
                const deviceId = pathname.replace('/devices/', '');
                const deviceName =
                    devicesDictionary[deviceId] !== undefined
                        ? devicesDictionary[deviceId].config.name
                        : '';
                name = 'Devices / ' + deviceName;
            } else if (pathname.startsWith('/developer/')) {
                name = 'Developer / Custom';
            }
        }
        return name;
    }

    render() {
        const { classes } = this.props;

        return (
            <AppBar className={classes.appBar}>
                <Toolbar>
                    <Typography variant="h2" color="textPrimary" className={classes.flex}>
                        {this.getPageName()}
                    </Typography>
                    <Hidden mdUp>
                        <IconButton
                            color="inherit"
                            aria-label="open drawer"
                            onClick={this.props.handleDrawerToggle}
                        >
                            <Menu />
                        </IconButton>
                    </Hidden>
                </Toolbar>
            </AppBar>
        );
    }
}

Header.propTypes = {
    classes: PropTypes.object.isRequired,
    devicesDictionary: PropTypes.object.isRequired,
};
export default withStyles(styles)(Header);
