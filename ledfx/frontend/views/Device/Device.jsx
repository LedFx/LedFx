import React from "react";
import PropTypes from "prop-types";

import Grid from "@material-ui/core/Grid";
import Card from "@material-ui/core/Card";
import CardContent from "@material-ui/core/CardContent";

import { callApi, getDevice } from "frontend/utils/api";
import EffectControl from "frontend/components/EffectControl/EffectControl.jsx";
import PixelColorGraph from "frontend/components/PixelColorGraph/PixelColorGraph.jsx";

class DeviceView extends React.Component {
  constructor() {
    super();
    this.state = {
      device: ""
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

  render() {
    const { classes } = this.props;
    const { device_id } = this.props.match.params;
    return (
      <Grid container spacing={24}>
        <Grid item xs={12}>
          <EffectControl deviceId={device_id} />
        </Grid>
        <Grid item xs={12}>
          <PixelColorGraph deviceId={device_id}/>
        </Grid>
      </Grid>
    );
  }
}

export default DeviceView;
