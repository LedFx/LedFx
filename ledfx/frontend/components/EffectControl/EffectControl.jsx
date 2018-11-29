import React from "react";
import PropTypes from "prop-types";
import { connect } from "react-redux";
import fetch from "cross-fetch";
import withStyles from "@material-ui/core/styles/withStyles";

import {
  fetchDeviceEffects
} from "frontend/actions";

import Grid from "@material-ui/core/Grid";
import Card from "@material-ui/core/Card";
import CardContent from "@material-ui/core/CardContent";
import Button from "@material-ui/core/Button";

import SchemaFormCollection from "frontend/components/SchemaForm/SchemaFormCollection.jsx";


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
    console.log(this.props.device)
    this.props.dispatch(fetchDeviceEffects(this.props.device.id));
  }

  handleClearEffect = () => {
    fetch(
      `${window.location.protocol}//${window.location.host}/api/devices/${
        this.props.device.id}/effects`,
      {
      method: "DELETE"
      }
    );
  };

  handleSetEffect = (type, config) => {
    if (!type) {
      return this.handleClearEffect()
    }

    fetch(
      `${window.location.protocol}//${window.location.host}/api/devices/${
        this.props.device.id}/effects`,
      {
        method: "PUT",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          type: type,
          config: config
        })
      }
    );
  };

  render() {
    const { classes, schemas } = this.props;

    if (schemas.effects) {
    return (
      <Card>
        <CardContent>
          <SchemaFormCollection
            schemaCollection={schemas.effects}
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
        </CardContent>
      </Card>
    );
  }

  return (<p>Loading</p>)
  }
}

EffectControl.propTypes = {
  classes: PropTypes.object.isRequired,
  schemas: PropTypes.object.isRequired,
  device: PropTypes.object.isRequired
};

function mapStateToProps(state) {
  const { schemas } = state;

  return {
    schemas
  };
}

export default connect(mapStateToProps)(withStyles(styles)(EffectControl));
