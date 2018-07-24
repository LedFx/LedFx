import React from "react";
import classNames from "classnames";
import PropTypes from "prop-types";

import withStyles from "@material-ui/core/styles/withStyles";
import AppBar from "@material-ui/core/AppBar";
import Toolbar from "@material-ui/core/Toolbar";
import IconButton from "@material-ui/core/IconButton";
import Hidden from "@material-ui/core/Hidden";
import Button from "@material-ui/core/Button";
import Typography from "@material-ui/core/Typography";
import Menu from "@material-ui/icons/Menu";

import headerStyle from "./style.jsx";
import viewRoutes from "frontend/routes/views.jsx";

class Header extends React.Component {

  getPageName() {
    var name;
    viewRoutes.map((prop, key) => {
      if (prop.path === this.props.location.pathname) {
        name = prop.navbarName;
      }
      return null;
    });
    return name;
  }

  render() {
    const { classes, color } = this.props;

    return (
      <AppBar className={classes.appBar}>
        <Toolbar>
          <Typography variant="title" color="inherit" className={classes.flex}>
            {this.getPageName()}
          </Typography>
          <Hidden mdUp>
            <IconButton
              color="inherit"
              aria-label="open drawer"
              onClick={this.props.handleDrawerToggle}>
              <Menu />
            </IconButton>
          </Hidden>
        </Toolbar>
      </AppBar>
    );
  }
}

Header.propTypes = {
  classes: PropTypes.object.isRequired
};

export default withStyles(headerStyle)(Header);
