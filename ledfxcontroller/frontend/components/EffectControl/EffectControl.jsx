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

import SchemaForm from 'frontend/components/SchemaForm/SchemaForm.jsx'
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
    marginBottom: theme.spacing.unit * 2,
    float: 'right',
    display: 'inline-block'
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

  handleSetEffect = value => {

    const data = {
      type: this.state.effectType,
      config: value,
    }
    console.log(value)
    fetch(`http://127.0.0.1:8888/api/devices/${this.props.deviceId}/effects`, {
        method: 'PUT',
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(data)
        })
  };

  render() {
    const { classes, effects } = this.props;

    if (effects) {
      var properties = this.state.effectType !== "" ? 
        effects[this.state.effectType].schema['properties'] : {};

      return (
        <Card>
          <CardContent>
          <FormControl className={classes.formControl}>
            <InputLabel htmlFor="effect-simple">Effect Type</InputLabel>
            <Select
              value={this.state.effectType}
              onChange={this.handleChangeSelectedEffect}
              inputProps={{
                name: "effectType",
                id: "effect-simple"
              }}>
              <MenuItem value="">
                <em>None</em>
              </MenuItem>
              {Object.keys(effects).map((effect_type, effect) => {
                return <MenuItem key={effect_type} value={effect_type}>{effect_type}</MenuItem>;
              })}
            </Select>
            </FormControl>
              <SchemaForm onSubmit={this.handleSetEffect} submitText="Set Effect" properties={properties}/>
              <Button className={classes.button} onClick={this.handleClearEffect}>Clear Effect</Button>
              <br/>
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
  effects: PropTypes.object.isRequired,
  devicesById: PropTypes.object.isRequired,
  deviceId: PropTypes.string.isRequired
};

function mapStateToProps(state) {
  const { devicesById, effects } = state

  return {
    devicesById,
    effects
  }
}

export default  connect(mapStateToProps)(withStyles(styles)(EffectControl));