import React from "react";
import PropTypes from "prop-types";

import Grid from "@material-ui/core/Grid";
import Card from "@material-ui/core/Card";
import CardHeader from "@material-ui/core/CardHeader";
import CardContent from "@material-ui/core/CardContent";
import CardActions from "@material-ui/core/CardActions";

import { getDevice, getDeviceEffects} from "frontend/utils/api";
import { connect } from "react-redux";
import EffectControl from "frontend/components/EffectControl/EffectControl.jsx";
import PixelColorGraph from "frontend/components/PixelColorGraph/PixelColorGraph.jsx";
import PresetsCard from "frontend/components/PresetsCard/PresetsCard.jsx";

class DeviceView extends React.Component {
  constructor() {
    super();
    this.state = {
      device : null,
      effect : null
    };
  }

  componentDidMount() {
    const { device_id } = this.props.match.params;

    this.state.device = null;
    getDevice(device_id)
      .then(device => {
        this.setState({ device: device });
      })
      .catch(error => console.log(error));

    this.state.effect = null;
    getDeviceEffects(device_id)
      .then(effect => {
        this.setState({ effect: effect });
      })
      .catch(error => console.log(error));
  }

  componentWillReceiveProps(nextProps) {
    var device = null;
    if (this.props.devicesById)
    {
      this.state.device = null;
      device = this.props.devicesById[nextProps.match.params.device_id]
      this.setState(...this.state, {device: device});
    }

    if(device !== undefined && device !== null)
    {
      this.state.effect = null;
      getDeviceEffects(device.id)
      .then(effect => {
        this.setState({ effect });
      })
      .catch(error => console.log(error));
    }
  
  }

  render() {
    const { classes } = this.props;
    const { device_id } = this.props.match.params;
    const { device, effect } = this.state;

    if (device)
    {
      return (
        <Grid container direction="row" spacing={4}>
          {renderPixelGraph(device, effect)}
          <Grid item xs={6}>
            <Card variant="outlined">
              <CardHeader title="Effect Control" subheader="Select an effect. Adjust settings manually, or choose a preset." />
              <CardContent>
                <EffectControl device={device} effect={effect}/>
              </CardContent>
            </Card>
          </Grid>
          {renderPresetsCard(device)}
        </Grid>
      );
    }
    return (<p>Loading</p>)
  }
}

const renderPixelGraph = (device, effect) => {
  if (device.effect && device.effect.name) {
    return (
      <Grid item xs={12}>
        <Card variant="outlined">
          <CardContent>
            <PixelColorGraph device={device}/>
          </CardContent>
        </Card>
      </Grid>
    )
  }
}

const renderPresetsCard = (device) => {
  if (device.effect && device.effect.name) {
    return (
      <Grid item xs={6}>
        <PresetsCard device={device}/>
      </Grid>
    )
  } else {
    return null
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
