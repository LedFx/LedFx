import React from "react";
import PropTypes from "prop-types";
import withStyles from "@material-ui/core/styles/withStyles";
import { connect } from "react-redux";

import Card from "@material-ui/core/Card";
import CardContent from "@material-ui/core/CardContent";
import Button from "@material-ui/core/Button";
import Switch from '@material-ui/core/Switch';
import TableRow from '@material-ui/core/TableRow';
import TableCell from '@material-ui/core/TableCell';
import { NavLink } from "react-router-dom";

import { setDeviceEffect } from "frontend/actions";

const styles = theme => ({
  button: {
    margin: theme.spacing.unit,
    float: "right"
  },
  submitControls: {
    margin: theme.spacing.unit,
    display: "block",
    width: "100%"
  },
  tableCell: {
    lineHeight: "1.2",
    padding: "12px 8px",
    verticalAlign: "middle"
  },
  deviceLink: {
    textDecoration: "none",
    "&,&:hover": {
      color: "#000000"
    }
  }
});

class DeviceMiniControl extends React.Component {

  isDeviceOn = () => {
    return this.props.device.effect && this.props.device.effect.name;
  }

  toggleOn = () => {
    if (this.isDeviceOn())
    {
      this.props.dispatch(setDeviceEffect(this.props.device.id, null, null));
    }
    else
    {
      this.props.dispatch(setDeviceEffect(this.props.device.id, 'wavelength', null));
    }
  }

  render() {
    const { classes, device } = this.props;

    return (
      <TableRow key={device.id}>
      <TableCell component="th" scope="row">
        <h1>{device.config.name}</h1>
      </TableCell>
      <TableCell className={classes.tableCell} numeric>
        <Button 
        component={NavLink}
        to={'/devices/' + device.id}
        className={classes.deviceLink}
        key={device.id}>
          Change Effect
        </Button>
      </TableCell>
      <TableCell className={classes.tableCell} numeric>
        <Switch
          checked={this.isDeviceOn()}
          onChange={this.toggleOn}
          color="primary"/>
      </TableCell>
      </TableRow>
    );
  }

}

DeviceMiniControl.propTypes = {
  classes: PropTypes.object.isRequired,
  device: PropTypes.object.isRequired
};

export default connect()(withStyles(styles)(DeviceMiniControl));
