import React from "react";
import PropTypes from "prop-types";

import Grid from "@material-ui/core/Grid";
import Card from "@material-ui/core/Card";
import CardContent from "@material-ui/core/CardContent";

import { callApi, getDevice } from "frontend/utils/api";
import { connect } from "react-redux";
import EffectControl from "frontend/components/EffectControl/EffectControl.jsx";
import PixelColorGraph from "frontend/components/PixelColorGraph/PixelColorGraph.jsx";

class DeviceView extends React.Component {
  constructor() {
    super();
    this.state = {
      device: null
    };
  }

  componentDidMount() {
    const { device_id } = this.props.match.params;

    getDevice(device_id)
      .then(device => {
        this.setState({ device: device });
      })
      .catch(error => console.log(error));
  }

  componentWillReceiveProps(nextProps) {
    var device = null;
    if (this.props.devicesById)
    {
      device = this.props.devicesById[nextProps.match.params.device_id]
    }
    this.setState(...this.state, {device: device});
  }

  render() {
    const { classes } = this.props;
    const { device_id } = this.props.match.params;
    const { device } = this.state;

    if (device)
    {
      return (
        <Grid container spacing={24}>
          <Grid item xs={12}>
            <EffectControl device={device} />
          </Grid>
          <Grid item xs={12}>
            <PixelColorGraph device={device}/>
          </Grid>
        </Grid>
      );
    }
    return (<p>Loading</p>)
  }
}

DeviceView.propTypes = {
  devicesById: PropTypes.object.isRequired,
};

function mapStateToProps(state) {
  const { devicesById } = state

  return {
    devicesById
  }
}

export default  connect(mapStateToProps)(DeviceView);
