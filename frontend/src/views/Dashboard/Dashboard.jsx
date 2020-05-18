import React from "react";
import PropTypes from "prop-types";
import { connect } from "react-redux";
import withStyles from "@material-ui/core/styles/withStyles";

import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import Grid from "@material-ui/core/Grid";

import PixelColorGraph from "components/PixelColorGraph/PixelColorGraph";
import DeviceMiniControl from 'components/DeviceMiniControl/DeviceMiniControl';
import AddPresetCard from "components/AddPresetCard/AddPresetCard";

const styles = theme => ({
  root: {
    flexGrow: 1
  },
  card: {
    width: "100%",
    overflowX: "auto"
  },
  table: {
    width: "100%",
    maxWidth: "100%",
    backgroundColor: "transparent",
    borderSpacing: "0",
  },
});

class DashboardView extends React.Component {

  render() {
    const { classes, devicesById } = this.props;

    if (Object.keys(devicesById) === 0)
    {
      return (
        <div>
          <Card>
              <CardContent>
                <p>Looks like you have no devices! Go to 'Device Management' to add them</p>
              </CardContent>
          </Card>
        </div>
      );
    }

    return (
      <div>

        <Grid container direction="row" spacing={4}>
          {
            Object.keys(devicesById).map(id => {                      
              return (
                <Grid item lg={6}>
                  <Card className={classes.card}>
                    <CardContent>
                      <Grid container direction="row" spacing={1}>
                        <Grid item xs={12}>
                          <DeviceMiniControl key={id} device={devicesById[id]}/>
                        </Grid>
                        <Grid item xs={12}>
                          <PixelColorGraph device={devicesById[id]}/>
                        </Grid>
                      </Grid>
                    </CardContent>
                  </Card>
                </Grid>
              );
            })
          }
        </Grid>

        <Grid container direction="row" spacing={4}>
          <Grid item xs={12}>
            <AddPresetCard />
          </Grid>
        </Grid>
      </div>
    );
  }
}

DashboardView.propTypes = {
  devicesById: PropTypes.object.isRequired,
};

function mapStateToProps(state) {
  const { devicesById } = state

  return {
    devicesById
  }
}

export default  connect(mapStateToProps)(withStyles(styles)(DashboardView));
