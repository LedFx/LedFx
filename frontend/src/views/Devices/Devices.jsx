import React from "react";
import withStyles from "@material-ui/core/styles/withStyles";

import Grid from "@material-ui/core/Grid";
import Card from "@material-ui/core/Card";
import CardContent from "@material-ui/core/CardContent";
import Button from "@material-ui/core/Button";
import AddIcon from "@material-ui/icons/Add";

import DevicesTable from "components/DevicesTable/DevicesTable.jsx";
import DeviceConfigDialog from "components/DeviceConfigDialog/DeviceConfigDialog.jsx";

const styles = theme => ({
  cardResponsive: {
    width: "100%",
    overflowX: "auto"
  },
  button: {
    position: "absolute",
    bottom: theme.spacing.unit * 2,
    right: theme.spacing.unit * 2
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
    this.setState({ addDialogOpened: true });
  };

  closeAddDeviceDialog = () => {
    this.setState({ addDialogOpened: false });
  };

  render() {
    const { classes } = this.props;
    return (
      <div>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={12} md={12}>
            <Card>
              <CardContent>
                <DevicesTable />
              </CardContent>
            </Card>
          </Grid>
        </Grid>
        <Button
          variant="fab"
          color="primary"
          aria-label="Add"
          className={classes.button}
          onClick={this.openAddDeviceDialog}
        >
          <AddIcon />
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
