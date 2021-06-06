import React, { useState } from 'react';
import { useSelector, useDispatch } from 'react-redux'
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
import WarningIcon from '@material-ui/icons/Warning';
import DevIcon from '@material-ui/icons/DeveloperMode';
import viewRoutes from 'routes/views.jsx';
import { drawerWidth } from 'utils/style';
import { Pause, PlayArrow } from '@material-ui/icons';
import { displaysPauseReceived } from 'modules/displays';
import { togglePause } from 'proxies/display';
import { Button } from '@material-ui/core';

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
    const paused = useSelector(state => state.displays.paused)
    const dispatch = useDispatch()
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
                        <Button
                            variant="contained"
                            color="primary"
                            size="medium"
                            onDoubleClick={() => {
                                console.log(name)
                                if ((name === 'Settings') && window.localStorage.getItem('BladeMod') < 1) {
                                    window.localStorage.setItem('BladeMod', 1);
                                    window.location.pathname = '/settings';
                                    return;
                                }
                                if (
                                    name === 'Settings' &&
                                    window.localStorage.getItem('BladeMod') === '1' &&
                                    window.localStorage.getItem('blade') === '3'
                                ) {
                                    window.localStorage.setItem('BladeMod', 2);
                                    window.location.pathname = '/settings';
                                    return;
                                }
                                window.localStorage.setItem('BladeMod', 0);
                                window.location.pathname = '/dashboard';
                            }}
                        >
                            {window.localStorage.getItem('BladeMod') === '1' ? (
                                <DevIcon />
                            ) : parseInt(window.localStorage.getItem('BladeMod')) === "2" ? (
                                <StarIcon />
                            ) : parseInt(window.localStorage.getItem('BladeMod')) > "2" ? (
                                <WarningIcon />
                            ) : (<RedeemIcon />)}
                        </Button>
                    )}
                    <Button
                        variant="contained"
                        color="primary"
                        size="medium"
                        onClick={async () => {
                            try {
                                const response = await togglePause();
                                if (response.statusText === 'OK') {
                                    dispatch(displaysPauseReceived(response.data.paused));
                                }
                            } catch (error) {
                                console.log('Error toggeling pause', error.message);
                            }
                        }}
                        style={{ margin: '0 1rem' }}
                    >
                        {!paused ? <Pause /> : <PlayArrow />}
                    </Button>
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
