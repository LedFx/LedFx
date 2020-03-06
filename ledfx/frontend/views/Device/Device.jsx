import React from "react";
import PropTypes from "prop-types";

import Grid from "@material-ui/core/Grid";
import Card from "@material-ui/core/Card";
import CardContent from "@material-ui/core/CardContent";

import { callApi, getDevice, getDeviceEffects} from "frontend/utils/api";
import { connect } from "react-redux";
import EffectControl from "frontend/components/EffectControl/EffectControl.jsx";
import PixelColorGraph from "frontend/components/PixelColorGraph/PixelColorGraph.jsx";
import MiniPresetsCard from "frontend/components/MiniPresetsCard/MiniPresetsCard.jsx";

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
        this.setState({ effect: effect });
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
          {renderMiniPresetsCard(device, effect)}
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <EffectControl device={device} effect={effect}/>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      );
    }
    return (<p>Loading</p>)
  }
}


const renderPixelGraph = (device, effect) => {
  if (device.effect && device.effect.name) {
    console.log(effect)
    return (
      <Grid item xs={12}>
        <Card>
          <CardContent>
            <PixelColorGraph device={device}/>
          </CardContent>
        </Card>
      </Grid>
    )
  }
}

const renderMiniPresetsCard = (device, effect) => {
  if (device.effect && device.effect.name) {
    console.log(effect)
    return (
      <Grid item xs={12}>
        <Card>
          <CardContent>
            <MiniPresetsCard device={device} effect={effect}/>
          </CardContent>
        </Card>
      </Grid>
    )
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
