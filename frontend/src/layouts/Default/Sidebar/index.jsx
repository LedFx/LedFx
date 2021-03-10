import React, { useEffect } from 'react';
import PropTypes from 'prop-types';
import { useSelector } from 'react-redux';
import { NavLink } from 'react-router-dom';
import withStyles from '@material-ui/core/styles/withStyles';
import Drawer from '@material-ui/core/Drawer';
import Hidden from '@material-ui/core/Hidden';
import List from '@material-ui/core/List';
import ListItem from '@material-ui/core/ListItem';
import ListItemIcon from '@material-ui/core/ListItemIcon';
import ListItemText from '@material-ui/core/ListItemText';
import viewRoutes from 'routes/views.jsx';
import logoAsset from 'assets/img/icon/large_white_alpha.png';
import sidebarStyle from './style.jsx';
import Icon from '@material-ui/core/Icon';
import { fetchDeviceList } from 'modules/devices.js';
import { fetchDisplayList } from 'modules/displays.js';
import { camelToSnake } from 'utils/helpers';

import BottomBar from './BottomBar.js';
import Wled from 'components/CustomIcons/Wled.js';
const Links = ({ classes, devMode, effectLinks, isViewActive }) => {
    const displays = useSelector(state => state.displays.list);

    return (
        <List className={classes.list}>
            {viewRoutes.map((prop, key) => {
                if (prop.redirect || !prop.sidebarName) {
                    return null;
                }

                if (prop.sidebarName === 'Developer' && !devMode) {
                    return null;
                }

                var listItemClass = classes.itemLink;
                if (isViewActive(prop.path) && prop.sidebarName !== 'Devices') {
                    listItemClass = listItemClass + ' ' + classes.activeView;
                }
                if (isViewActive(prop.path) && prop.sidebarName !== 'Displays') {
                    listItemClass = listItemClass + ' ' + classes.activeView;
                }
                if (isViewActive(prop.path) && prop.sidebarName !== 'EffectPresets') {
                    listItemClass = listItemClass + ' ' + classes.activeView;
                }

                if (prop.sidebarName === 'Displays') {
                    return (
                        <div className={classes.item} key={key}>
                            <ListItem button className={listItemClass} key={prop.sidebarName}>
                                <NavLink
                                    to={`/devices`}
                                    className={classes.item}
                                    activeClassName="active"
                                >
                                    <ListItemIcon className={classes.itemIcon}>
                                        <prop.icon />
                                    </ListItemIcon>
                                    <ListItemText
                                        primary={'Devices'}
                                        className={classes.itemText}
                                        disableTypography={true}
                                    />
                                </NavLink>
                                <List className={classes.list}>
                                    {displays.map(display => {
                                        let listItemClass = classes.itemLink;
                                        if (isViewActive(`/displays/${display.id}`)) {
                                            listItemClass = `${listItemClass} ${classes.activeView}`;
                                        }
                                        return (
                                            <NavLink
                                                to={`/displays/${display.id}`}
                                                className={classes.item}
                                                key={display.id}
                                                activeClassName="active"
                                            >
                                                <ListItem button className={listItemClass}>
                                                    <ListItemIcon className={classes.itemIcon}>
                                                        <Icon
                                                            color={
                                                                display.effect &&
                                                                    display.effect.active === true
                                                                    ? isViewActive(
                                                                        `/displays/${display.id}`
                                                                    )
                                                                        ? 'inherit'
                                                                        : 'primary'
                                                                    : 'inherit'
                                                            }
                                                            style={{ position: 'relative' }}
                                                        >
                                                            {display.config.icon_name &&
                                                                display.config.icon_name.startsWith(
                                                                    'wled'
                                                                ) ? (
                                                                    <Wled />
                                                                ) : display.config.icon_name.startsWith(
                                                                    'mdi:'
                                                                ) ? (
                                                                        <span
                                                                            className={`mdi mdi-${display.config.icon_name.split(
                                                                                'mdi:'
                                                                            )[1]
                                                                                }`}
                                                                        ></span>
                                                                    ) : (
                                                                        camelToSnake(
                                                                            display.config.icon_name ||
                                                                            'SettingsInputComponent'
                                                                        )
                                                                    )}
                                                        </Icon>
                                                    </ListItemIcon>
                                                    <ListItemText
                                                        primary={display.config.name}
                                                        className={classes.devicesItemText}
                                                        disableTypography={true}
                                                    />
                                                </ListItem>
                                            </NavLink>
                                        );
                                    })}
                                </List>
                            </ListItem>
                        </div>
                    );
                }

                if (prop.sidebarName === 'EffectPresets') {
                    return (
                        <ListItem button className={listItemClass}>
                            <ListItemIcon className={classes.itemIcon}>
                                <prop.icon />
                            </ListItemIcon>
                            <ListItemText
                                primary={prop.sidebarName}
                                className={classes.itemText}
                                disableTypography={true}
                            />
                            <List className={classes.list}>{effectLinks}</List>
                        </ListItem>
                    );
                }

                return (
                    <NavLink
                        to={prop.path}
                        className={classes.item}
                        activeClassName="active"
                        key={key}
                    >
                        <ListItem button className={listItemClass}>
                            <ListItemIcon className={classes.itemIcon}>
                                <prop.icon />
                            </ListItemIcon>
                            <ListItemText
                                primary={prop.sidebarName}
                                className={classes.itemText}
                                disableTypography={true}
                            />
                        </ListItem>
                    </NavLink>
                );
            })}
        </List>
    );
};

const Sidebar = props => {
    const isViewActive = viewName => {
        return props.location.pathname === viewName;
    };

    const { classes, effectLinks, devMode, handleDrawerToggle, open } = props;
    const version = useSelector(state => state.settings.version);
    const logo = (
        <div className={classes.logo}>
            <a href="/#" className={classes.logoLink}>
                <div className={classes.logoImage}>
                    <img src={logoAsset} alt="logo" className={classes.img} />
                </div>
                LedFx
                <span style={{ fontSize: 'small', color: '#999' }}> - v{version}</span>
            </a>
            {((parseInt(window.localStorage.getItem('BladeMod')) > 0) || window.ledfx_mode === 'dev')
                && (<div className={classes.devbadge} onClick={() => {
                    if (parseInt(window.localStorage.getItem('BladeMod')) === 1 && props.location.pathname === '/devices') {
                        window.location = '/advanced'
                    }
                }}>v{process.env.REACT_APP_VERSION}</div>)}


        </div >
    );
    useEffect(() => {
        fetchDisplayList();
        fetchDeviceList();
    }, []);

    return (
        <div>
            <Hidden mdUp>
                <Drawer
                    variant="temporary"
                    anchor="right"
                    open={open}
                    classes={{
                        paper: classes.drawerPaper,
                    }}
                    onClose={handleDrawerToggle}
                    ModalProps={{
                        keepMounted: true,
                    }}
                >
                    {logo}
                    <div className={classes.sidebarWrapper}>
                        <Links
                            isViewActive={isViewActive}
                            classes={classes}
                            effectLinks={effectLinks}
                            devMode={devMode}
                        />
                        <BottomBar classes={classes} />
                    </div>
                    <div className={classes.background} />
                </Drawer>
            </Hidden>
            <Hidden smDown implementation="css">
                <Drawer
                    open
                    variant="permanent"
                    classes={{
                        paper: classes.drawerPaper,
                    }}
                >
                    {logo}
                    <div className={classes.sidebarWrapper}>
                        <Links
                            isViewActive={isViewActive}
                            classes={classes}
                            effectLinks={effectLinks}
                            devMode={devMode}
                        />
                        <BottomBar classes={classes} />
                    </div>
                    <div className={classes.background} />
                </Drawer>
            </Hidden>
        </div>
    );
};

Sidebar.propTypes = {
    classes: PropTypes.object.isRequired,
};

export default withStyles(sidebarStyle)(Sidebar);
