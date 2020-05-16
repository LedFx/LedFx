import React from "react";
import PropTypes from "prop-types";
import { connect } from "react-redux";
import withStyles from "@material-ui/core/styles/withStyles";


import Typography from "@material-ui/core/Typography";
import Grid from "@material-ui/core/Grid";
import Card from "@material-ui/core/Card";
import CardContent from "@material-ui/core/CardContent";
import Button from "@material-ui/core/Button";

import SchemaFormCollection from "../../components/SchemaForm/SchemaFormCollection.jsx";
            import {
              setDeviceEffect,
              fetchDeviceEffects
            } from "../../actions";

const styles = theme => ({
  button: {
    margin: theme.spacing.unit,
    float: "right"
  },
  submitControls: {
    margin: theme.spacing.unit,
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

  render() {
    const { classes, schemas, effect } = this.props;
    
    if (schemas.effects) {
    var effectvalue = "";
    if(effect !== undefined  && effect !== null && effect.effect !== null)
      effectvalue = effect.effect.type;
    return (
      <div>
        <Typography variant="h5" color="inherit">
          Effect Control
        </Typography>
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
