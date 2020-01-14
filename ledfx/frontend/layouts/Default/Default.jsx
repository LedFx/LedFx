import React from "react";
import { connect } from "react-redux";
import {
  fetchDeviceList,
  fetchSchemasIfNeeded
} from "frontend/actions";
import PropTypes from "prop-types";
import { Switch, Route, Redirect } from "react-router-dom";

import Header from "frontend/components/Header/Header.jsx";
import Sidebar from "frontend/components/Sidebar/Sidebar.jsx";
import withStyles from "@material-ui/core/styles/withStyles";
import viewRoutes from "frontend/routes/views.jsx";
import dashboardStyle from "./style.jsx";
import logo from "frontend/assets/img/icon/small_white_alpha.png";

import { MuiThemeProvider, createMuiTheme } from "@material-ui/core/styles";
import cyan from "@material-ui/core/colors/cyan";
import green from "@material-ui/core/colors/green";

import CssBaseline from "@material-ui/core/CssBaseline";

const defaultTheme = createMuiTheme({
  palette: {
    primary: cyan,
    secondary: green
  },
  overrides: {
      MuiFormControl: {
        root: {
          margin: 8,
          minWidth: 225,
          flex: "1 0 30%"
        },
      },
    },
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
        var newState = Object.assign({}, this.state, { mobileOpen: false });
        this.setState(newState);
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
      var newState = Object.assign({}, this.state, {
        mobileOpen: !this.state.mobileOpen
      });
      this.setState(newState);
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
  devicesById: PropTypes.object.isRequired
};

function mapStateToProps(state) {
  const { devicesById, schemas } = state;

  return {
    devicesById,
    schemas
  };
}

export default connect(mapStateToProps)(
  withStyles(dashboardStyle)(DefaultLayout)
);
