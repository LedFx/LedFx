import React from "react";
import PropTypes from "prop-types";
import withStyles from "@material-ui/core/styles/withStyles";
import { connect } from "react-redux";

import Button from "@material-ui/core/Button";
import Dialog from "@material-ui/core/Dialog";
import DialogContent from "@material-ui/core/DialogContent";
import DialogTitle from "@material-ui/core/DialogTitle";
import DialogActions from "@material-ui/core/DialogActions";
import DialogContentText from "@material-ui/core/DialogContentText";

import SchemaFormCollection from "frontend/components/SchemaForm/SchemaFormCollection.jsx";
import { addDevice } from"frontend/actions";

import fetch from "cross-fetch";

const styles = theme => ({
  button: {
    float: "right"
  }
});

class ScenesConfigDialog extends React.Component {
  constructor(props) {
    super(props);
  }

  handleClose = () => {
    this.props.onClose();
  };

  handleSubmit = (type, config) => {
    this.props.dispatch(addDevice(type, config));
    this.props.onClose();
  };

  render() {
    const { classes, dispatch, schemas, onClose, ...otherProps } = this.props;
    return (
      <Dialog
        onClose={this.handleClose}
        className={classes.cardResponsive}
        aria-labelledby="form-dialog-title"
        {...otherProps}
      >
        <DialogTitle id="form-dialog-title">Add Scene</DialogTitle>
        <DialogContent className={classes.cardResponsive}>
          <DialogContentText>
            To add a scene to LedFx, please first configure the effects you wish to save,
            select the type of scene you wish, and then provide the necessary configuration.
          </DialogContentText>
          <SchemaFormCollection
            schemaCollection={schemas.devices}
            onSubmit={this.handleSubmit}
            useAdditionalProperties={true}
          >
            <Button
              className={classes.button}
              type="submit"
              color="primary"
            >
              Add
            </Button>
            <Button
              className={classes.button}
              onClick={this.handleClose}
              color="primary"
            >
              Cancel
            </Button>
          </SchemaFormCollection>
        </DialogContent>
      </Dialog>
    );
  }
}

function mapStateToProps(state) {
  const { schemas } = state;

  return {
    schemas
  };
}

export default connect(mapStateToProps)(withStyles(styles)(ScenesConfigDialog));
