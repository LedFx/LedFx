import React from "react";
import PropTypes from "prop-types";

import Grid from "@material-ui/core/Grid";
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';

import { callApi, getDevice } from 'frontend/utils/api'

const baseStyle = theme => ({
    cardResponsive: {
        width: "100%",
        marginTop: theme.spacing.unit * 3,
        overflowX: "auto"
    },
})



class DeviceView extends React.Component {

  constructor(){
    super()
    this.state={
      device:''
    }
  }

  componentDidMount() {
    const { device_id } = this.props.match.params;
  
    getDevice(device_id).then(device => {
      this.setState({ device: device });
    }).catch(error => console.log(error));
  
  }

  render() {
    const { classes } = this.props;
    const { device_id } = this.props.match.params;
    return (
      <div>
        <Card>
            <CardContent><p>{this.state.device.name}</p></CardContent>
        </Card>
      </div>

    );
  }
}



export default DeviceView;
