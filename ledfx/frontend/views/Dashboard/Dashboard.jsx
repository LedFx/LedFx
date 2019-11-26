import React from "react";
import PropTypes from "prop-types";
import { connect } from "react-redux";
import withStyles from "@material-ui/core/styles/withStyles";

import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import Typography from '@material-ui/core/Typography';

import Table from '@material-ui/core/Table';
import TableBody from '@material-ui/core/TableBody';
import Grid from "@material-ui/core/Grid";
import PixelColorGraph from "frontend/components/PixelColorGraph/PixelColorGraph.jsx";
import DeviceMiniControl from 'frontend/components/DeviceMiniControl/DeviceMiniControl.jsx'

const styles = theme => ({
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

    if (Object.keys(devicesById) == 0)
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
        <Card>
            <CardContent>
              <Table className={classes.table}>
                <TableBody width="50%">
                  {
                    Object.keys(devicesById).map(id => {                      
                      return (
                        <div>
                          <Grid container spacing={24}>
                            <Grid item xs={12}>
                              <PixelColorGraph device={devicesById[id]}/>
                            </Grid>
                          </Grid>
                          <DeviceMiniControl key={id} device={devicesById[id]}/>                        
                        </div>
                      );
                    })
                  }
                </TableBody>
              </Table>
            </CardContent>
        </Card>
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
