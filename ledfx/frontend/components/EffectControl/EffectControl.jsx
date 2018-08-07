import React from "react";
import PropTypes from "prop-types";
import { connect } from "react-redux";
import fetch from "cross-fetch";
import withStyles from "@material-ui/core/styles/withStyles";

import Grid from "@material-ui/core/Grid";
import Card from "@material-ui/core/Card";
import CardContent from "@material-ui/core/CardContent";
import Button from "@material-ui/core/Button";

import SchemaFormCollection from "frontend/components/SchemaForm/SchemaFormCollection.jsx";


const styles = theme => ({
  button: {
    margin: theme.spacing.unit,
    float: "right"
  }
});

class EffectControl extends React.Component {

  handleClearEffect = () => {
    fetch(`http://127.0.0.1:8888/api/devices/${this.props.deviceId}/effects`, {
      method: "DELETE"
    });
  };

  handleSetEffect = (type, config) => {
    console.log("handleSetEffect", type, config);
    fetch(
      `${window.location.protocol}//${window.location.host}/api/devices/${
        this.props.deviceId
      }/effects`,
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
  deviceId: PropTypes.string.isRequired
};

function mapStateToProps(state) {
  const { schemas } = state;

  return {
    schemas
  };
}

export default connect(mapStateToProps)(withStyles(styles)(EffectControl));
