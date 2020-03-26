import React from "react";
import PropTypes from "prop-types";
import { connect } from "react-redux";
import withStyles from "@material-ui/core/styles/withStyles";

import {
  setDeviceEffect,
  fetchDeviceEffects,
  RANDOMIZE_EFFECT
} from "frontend/actions";

import Grid from "@material-ui/core/Grid";
import Card from "@material-ui/core/Card";
import CardContent from "@material-ui/core/CardContent";
import Button from "@material-ui/core/Button";
import SchemaFormCollection from "frontend/components/SchemaForm/SchemaFormCollection.jsx";
import Typography from "@material-ui/core/Typography";

const styles = theme => ({
  button: {
    margin: theme.spacing(1),
    float: "right"
  },
  submitControls: {
    display: "block",
    width: "100%"
  },
});


class EffectControl extends React.Component {

  componentDidMount() {
    this.props.dispatch(fetchDeviceEffects(this.props.device.id));
  }

  handleClearEffect = () => {
    this.props.dispatch(setDeviceEffect(this.props.device.id, null, null))
  };

  handleSetEffect = (type, config) => {
    this.props.dispatch(setDeviceEffect(this.props.device.id, type, config))
  };

  handleRandomizeEffect = () => {
    this.props.dispatch(setDeviceEffect(this.props.device.id, null, RANDOMIZE_EFFECT))
  };

  render() {
    const { classes, schemas, effect } = this.props;
    
    if (schemas.effects) {
    var effectvalue = "";
    if(effect !== undefined  && effect !== null && effect.effect !== null)
      effectvalue = effect.effect.type;
    return (
      <div>
        <SchemaFormCollection
          schemaCollection={schemas.effects}
          currentEffect={effect}
          onSubmit={this.handleSetEffect}
        >
        <div className={classes.submitControls}>
          <Button
            className={classes.button}
            type="submit"
            variant="contained"
            color="primary"
          >
            Set Effect
          </Button>
          <Button
            className={classes.button}
            onClick={this.handleClearEffect}
            color="primary"
          >
            Clear Effect
          </Button>
          <Button
            className={classes.button}
            onClick={this.handleRandomizeEffect}
            color="primary"
          >
            Randomize
          </Button>
        </div>
        </SchemaFormCollection>
      </div>
    );
  }

  return (<p>Loading</p>)
  }
}

EffectControl.propTypes = {
  classes: PropTypes.object.isRequired,
  schemas: PropTypes.object.isRequired,
  device: PropTypes.object.isRequired,
  effect: PropTypes.object.isRequired
};

function mapStateToProps(state) {
  const { schemas } = state;

  return {
    schemas
  };
}

export default connect(mapStateToProps)(withStyles(styles)(EffectControl));
