import React from "react";
import PropTypes from "prop-types";
import { Switch, Route, Redirect } from "react-router-dom";

import Header from "frontend/components/Header/Header.jsx";
import Sidebar from "frontend/components/Sidebar/Sidebar.jsx";

import withStyles from "@material-ui/core/styles/withStyles";


import viewRoutes from "frontend/routes/views.jsx";


import dashboardStyle from "./style.jsx";
import logo from "frontend/assets/img/logo.png";


import { MuiThemeProvider, createMuiTheme } from '@material-ui/core/styles';
import cyan from '@material-ui/core/colors/cyan';
import green from '@material-ui/core/colors/green';

import CssBaseline from '@material-ui/core/CssBaseline';
import "frontend/style.css"


const switchViewRoutes = (
  <Switch>
    {
      viewRoutes.map((prop, key) => {
        if (prop.redirect) {
          return <Redirect from={prop.path} to={prop.to} key={key} />;
        }
        return <Route exact path={prop.path} component={prop.component} key={key} />;
      })
    }
  </Switch>
);


const defaultTheme = createMuiTheme({
  palette: {
    primary: cyan,
    secondary: green
  }
});

class DefaultLayout extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      mobileOpen: false,
      theme: defaultTheme
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

  render() {
    const { classes, rest } = this.props;

    var handleDrawerToggle = () => {
      this.setState({ mobileOpen: !this.state.mobileOpen });
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
            {switchViewRoutes}
          </div>
        </MuiThemeProvider>

      </div>
    );
  }
}

DefaultLayout.propTypes = {
  classes: PropTypes.object.isRequired
};

export default withStyles(dashboardStyle)(DefaultLayout);
