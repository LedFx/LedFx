import React from "react";
import PropTypes from "prop-types";
import { connect } from "react-redux";

import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import Typography from '@material-ui/core/Typography';

import DeviceMiniControl from 'frontend/components/DeviceMiniControl/DeviceMiniControl.jsx'

class DashboardView extends React.Component {

  render() {
    const { classes, devicesById } = this.props;
    return (
      <div>
        <Card>
            <CardContent>
              {
                Object.keys(devicesById).map(id => {
                  return (
                    <DeviceMiniControl key={id} device={devicesById[id]}/>
                  );
                })
              }
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

export default  connect(mapStateToProps)(DashboardView);
