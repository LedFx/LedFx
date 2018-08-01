import React from "react";
import PropTypes from "prop-types";

import Grid from "@material-ui/core/Grid";
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';

import DevicesTable from 'frontend/components/DevicesTable/DevicesTable.jsx'

import { callApi, getDevices } from 'frontend/utils/api'

const baseStyle = theme => ({
  cardResponsive: {
    width: "100%",
    marginTop: theme.spacing.unit * 3,
    overflowX: "auto"
  },
})



class DevicesView extends React.Component {

  constructor() {
    super()
    this.state = {
      devices: [],
    }
  }

  componentDidMount() {
    getDevices().then(devices => {
      this.setState({ devices: devices });
    }).catch(error => console.log(error));

  }

  render() {
    const { classes, devices } = this.props;
    return (
      <Grid container spacing={16}>
        <Grid item xs={12} sm={12} md={12}>
          <Card>
            <CardContent>
              <DevicesTable
                devices={this.state.devices}
              />
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    );
  }
}

export default DevicesView;
