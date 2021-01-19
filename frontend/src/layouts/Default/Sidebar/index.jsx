import React from 'react';
import PropTypes from 'prop-types';
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

class Sidebar extends React.Component {
    isViewActive(viewName) {
        return this.props.location.pathname === viewName;
    }

    render() {
        const { classes, devices, effectLinks, devMode, handleDrawerToggle, open } = this.props;

        var links = (
            <List className={classes.list}>
                {viewRoutes.map((prop, key) => {
                    if (prop.redirect || !prop.sidebarName) {
                        return null;
                    }

                    if (prop.sidebarName === 'Developer' && !devMode) {
                        return null;
                    }

                    var listItemClass = classes.itemLink;
                    if (this.isViewActive(prop.path) && prop.sidebarName !== 'Devices') {
                        listItemClass = listItemClass + ' ' + classes.activeView;
                    }
                    if (this.isViewActive(prop.path) && prop.sidebarName !== 'EffectPresets') {
                        listItemClass = listItemClass + ' ' + classes.activeView;
                    }

                    if (prop.sidebarName === 'Devices') {
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
                                            primary={prop.sidebarName}
                                            className={classes.itemText}
                                            disableTypography={true}
                                        />
                                    </NavLink>
                                    <List className={classes.list}>
                                        {devices.map(device => {
                                            let listItemClass = classes.itemLink;
                                            if (this.isViewActive(`/devices/${device.id}`)) {
                                                listItemClass = `${listItemClass} ${classes.activeView}`;
                                            }
                                            return (
                                                <NavLink
                                                    to={`/devices/${device.id}`}
                                                    className={classes.item}
                                                    key={device.id}
                                                    activeClassName="active"
                                                >
                                                    <ListItem button className={listItemClass}>
                                                        <ListItemText
                                                            primary={device.config.name}
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

        const logo = (
            <div className={classes.logo}>
                <a href="/#" className={classes.logoLink}>
                    <div className={classes.logoImage}>
                        <img src={logoAsset} alt="logo" className={classes.img} />
                    </div>
                    LedFx
                </a>
            </div>
        );

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
                        <div className={classes.sidebarWrapper}>{links}</div>
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
                        <div className={classes.sidebarWrapper}>{links}</div>
                        <div className={classes.background} />
                    </Drawer>
                </Hidden>
            </div>
        );
    }
}

Sidebar.propTypes = {
    classes: PropTypes.object.isRequired,
    devices: PropTypes.array.isRequired,
};

export default withStyles(sidebarStyle)(Sidebar);
