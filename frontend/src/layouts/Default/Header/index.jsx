import React, { useState } from 'react';
import PropTypes from 'prop-types';
import withStyles from '@material-ui/core/styles/withStyles';
import AppBar from '@material-ui/core/AppBar';
import Toolbar from '@material-ui/core/Toolbar';
import IconButton from '@material-ui/core/IconButton';
import Hidden from '@material-ui/core/Hidden';
import Typography from '@material-ui/core/Typography';
import Menu from '@material-ui/icons/Menu';
import RedeemIcon from '@material-ui/icons/Redeem';
import StarIcon from '@material-ui/icons/Star';
import DevIcon from '@material-ui/icons/DeveloperMode';
import viewRoutes from 'routes/views.jsx';
import { drawerWidth } from 'utils/style';
import Fab from '@material-ui/core/Fab';

const styles = theme => ({
    appBar: {
        backgroundColor: theme.palette.background.default,
        paddingLeft: 0,
        [theme.breakpoints.up('md')]: {
            width: `100%`,
            left: 0,
            paddingLeft: drawerWidth,
        },
    },
    // toolBar: {
    //     background: 'rgb(16,16,16)',
    //     bordeBottom: '1px solid rgba(255, 255, 255, 0.12)',
    // },
    flex: {
        flex: 1,
        fontSize: 18,
        fontWeight: 300,
    },
});

const Header = props => {
    const getPageName = () => {
        const { location, devicesDictionary, selectedDisplay } = props;
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
            } else if (pathname.startsWith('/displays/')) {
                const displayId = pathname.replace('/displays/', '');
                const displayName =
                    devicesDictionary[displayId] !== undefined
                        ? devicesDictionary[displayId].config.name
                        : selectedDisplay
                        ? selectedDisplay.config[selectedDisplay.id] &&
                          selectedDisplay.config[selectedDisplay.id].config.name
                        : '';

                name = 'Devices / ' + displayName;
            } else if (pathname.startsWith('/developer/')) {
                name = 'Developer / Custom';
            }
        }
        return name;
    };
    const [easterEgg, setEasterEgg] = useState(false);

    const { classes } = props;
    const name = getPageName();
    return (
        <AppBar className={classes.appBar}>
            <Toolbar className={classes.toolBar}>
                <>
                    <Typography
                        variant="h2"
                        color="textPrimary"
                        className={classes.flex}
                        onDoubleClick={() => {
                            if (name === 'Device Management') {
                                setEasterEgg(true);
                            }
                        }}
                    >
                        {getPageName()}
                    </Typography>
                    {(easterEgg || parseInt(window.localStorage.getItem('BladeMod')) > 0) && (
                        <Fab
                            variant="round"
                            color="primary"
                            size="small"
                            onDoubleClick={() => {
                                if (name === 'Settings') {
                                    window.localStorage.setItem('BladeMod', 1);
                                    window.location.pathname = '/settings';
                                    return;
                                }
                                if (
                                    name === 'Advanced' &&
                                    window.localStorage.getItem('BladeMod') === '1' &&
                                    window.localStorage.getItem('blade') === '3'
                                ) {
                                    window.localStorage.setItem('BladeMod', 2);
                                    window.location.pathname = '/advanced';
                                    return;
                                }
                                window.localStorage.setItem('BladeMod', 0);
                                window.location.pathname = '/dashboard';
                            }}
                        >
                            {window.localStorage.getItem('BladeMod') === '1' ? (
                                <DevIcon />
                            ) : parseInt(window.localStorage.getItem('BladeMod')) > 1 ? (
                                <StarIcon />
                            ) : (
                                <RedeemIcon />
                            )}
                        </Fab>
                    )}
                    <Hidden mdUp>
                        <IconButton aria-label="open drawer" onClick={props.handleDrawerToggle}>
                            <Menu />
                        </IconButton>
                    </Hidden>
                </>
            </Toolbar>
        </AppBar>
    );
};

Header.propTypes = {
    classes: PropTypes.object.isRequired,
    devicesDictionary: PropTypes.object.isRequired,
};
export default withStyles(styles)(Header);
