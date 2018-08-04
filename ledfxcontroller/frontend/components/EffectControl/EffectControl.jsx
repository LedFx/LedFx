import React from "react";
import PropTypes from "prop-types";
import { connect } from "react-redux";
import Grid from "@material-ui/core/Grid";
import Card from "@material-ui/core/Card";
import CardContent from "@material-ui/core/CardContent";
import Typography from "@material-ui/core/Typography";

import InputLabel from '@material-ui/core/InputLabel';
import MenuItem from '@material-ui/core/MenuItem';
import Select from '@material-ui/core/Select';
import FormControl from '@material-ui/core/FormControl';
import Button from '@material-ui/core/Button';
import withStyles from "@material-ui/core/styles/withStyles";

import SchemaFormCollection from 'frontend/components/SchemaForm/SchemaFormCollection.jsx'

import setDeviceEffect from 'frontend/actions'

import fetch from 'cross-fetch'
const onSubmit = ({ formData }) => console.log("Data submitted: ", formData);

const styles = theme => ({
  formControl: {
    margin: theme.spacing.unit,
    minWidth: 120,
    width: '100%'
  },
  button: {
    margin: theme.spacing.unit,
    float: 'right',
  }
});

class EffectControl extends React.Component {
  constructor(props) {
    super(props)

    this.state = {
      effectType: ""
    };

  }

  handleChangeSelectedEffect = (event) => {
    this.setState({ [event.target.name]: event.target.value });
  };

  handleClearEffect = () => {
    fetch(`http://127.0.0.1:8888/api/devices/${this.props.deviceId}/effects`, {
        method: 'DELETE'})
  };

  handleSetEffect = (type, config) => {
    console.log("handleSetEffect", type, config)
    fetch(`${window.location.protocol}//${window.location.host}/api/devices/${this.props.deviceId}/effects`, {
      method: 'PUT',
      headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        type: type,
        config: config,
      })
    })
  };

  render() {
    const { classes, schemas } = this.props;

    if (schemas.effects) {

      return (
        <Card>
          <CardContent>
            <SchemaFormCollection schemaCollection={schemas.effects} onSubmit={this.handleSetEffect}>
              <Button className={classes.button} type="submit" variant="contained" color="primary">
                Set Effect
              </Button>
              <Button className={classes.button} onClick={this.handleClearEffect} color="primary">
                Clear Effect
              </Button>
            </SchemaFormCollection>
          </CardContent>
        </Card>
      );
    }

    return (
      <Card>
        <CardContent>Nothing here</CardContent>
      </Card>
    );
  }
}

EffectControl.propTypes = {
  classes: PropTypes.object.isRequired,
  schemas: PropTypes.object.isRequired,
  devicesById: PropTypes.object.isRequired,
  deviceId: PropTypes.string.isRequired
};

function mapStateToProps(state) {
  const { devicesById, schemas } = state

  return {
    devicesById,
    schemas
  }
}

export default  connect(mapStateToProps)(withStyles(styles)(EffectControl));