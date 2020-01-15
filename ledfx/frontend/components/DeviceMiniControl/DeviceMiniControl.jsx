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
import Grid from "@material-ui/core/Grid";
import Typography from "@material-ui/core/Typography";
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
  },
  header: {
    margin: 0
  },
  subHeader: {
    margin: 0,
    color: "#333333"
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
      <Grid container direction="col" spacing={1}>
        <Grid item xs>
          <Typography variant="h5" color="inherit" className={classes.header}>
            {device.config.name}
          </Typography>
          <Typography variant="caption text" color="inherit" className={classes.subHeader}>
            Effect: {device.effect.name}
          </Typography>
        </Grid>
        {/* <Grid item xs>

        </Grid> */}
        <Grid item>
          <Button 
          component={NavLink}
          to={'/devices/' + device.id}
          className={classes.deviceLink}
          key={device.id}>
            Change Effect
          </Button>
        </Grid>
        <Grid>
          <Switch
            checked={this.isDeviceOn()}
            onChange={this.toggleOn}
            color="primary"/>
        </Grid>
      </Grid>
    );
  }

}

DeviceMiniControl.propTypes = {
  classes: PropTypes.object.isRequired,
  device: PropTypes.object.isRequired
};

export default connect()(withStyles(styles)(DeviceMiniControl));
