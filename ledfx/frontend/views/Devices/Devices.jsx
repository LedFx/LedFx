import React from "react";
import PropTypes from "prop-types";
import withStyles from "@material-ui/core/styles/withStyles";

import Typography from '@material-ui/core/Typography';
//import Slider from '@material-ui/core/Slider';
import Input from '@material-ui/core/Input';
import { connect } from "react-redux";

import Grid from "@material-ui/core/Grid";
import Card from "@material-ui/core/Card";
import CardHeader from "@material-ui/core/CardHeader";
import CardContent from "@material-ui/core/CardContent";
import Button from "@material-ui/core/Button";

import DevicesTable from "frontend/components/DevicesTable/DevicesTable.jsx";
import DeviceConfigDialog from "frontend/components/DeviceConfigDialog/DeviceConfigDialog.jsx";

const styles = theme => ({
  cardResponsive: {
    width: "100%",
    overflowX: "auto"
  },
  button: {
    position: "absolute",
    bottom: theme.spacing(2),
    right: theme.spacing(2)
  },
  dialogButton: {
    float: "right"
  }
});

class DevicesView extends React.Component {
  constructor(props) {
    super(props);

    this.state = {
      addDialogOpened: false
    };
  }

  openAddDeviceDialog = () => {
    this.setState(...this.state, { addDialogOpened: true });
  };

  closeAddDeviceDialog = () => {
    this.setState(...this.state, { addDialogOpened: false });
  };

  render() {
    const { classes, schemas } = this.props;
    return (
      <div>
        <Grid container spacing={16}>
          <Grid item xs={12} sm={12} md={12}>
            <Card variant="outlined">
              <CardHeader title="Devices" subheader="View and manage all your devices connected to LedFx" />
              <CardContent>
                <DevicesTable />
              </CardContent>
            </Card>
          </Grid>
        </Grid>
        <Button
          variant="contained"
          color="primary"
          aria-label="Add"
          className={classes.button}
          onClick={this.openAddDeviceDialog}
        >
          Add Device
        </Button>
        <DeviceConfigDialog
          open={this.state.addDialogOpened}
          onClose={this.closeAddDeviceDialog}
        />
      </div>
    );
  }
}

export default withStyles(styles)(DevicesView);
