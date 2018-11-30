import React from "react";
import PropTypes from "prop-types";
import { connect } from "react-redux";
import withStyles from "@material-ui/core/styles/withStyles";

import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import Typography from '@material-ui/core/Typography';

import Table from '@material-ui/core/Table';
import TableBody from '@material-ui/core/TableBody';

import DeviceMiniControl from 'frontend/components/DeviceMiniControl/DeviceMiniControl.jsx'

const styles = theme => ({
  table: {
    marginBottom: "0",
    width: "100%",
    maxWidth: "100%",
    backgroundColor: "transparent",
    borderSpacing: "0",
    borderCollapse: "collapse"
  }
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
                <TableBody>
                  {
                    Object.keys(devicesById).map(id => {
                      return (
                        <DeviceMiniControl key={id} device={devicesById[id]}/>
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
