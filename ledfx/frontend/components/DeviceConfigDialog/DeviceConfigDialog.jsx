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

class DeviceConfigDialog extends React.Component {
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
        <DialogTitle id="form-dialog-title">Add Device</DialogTitle>
        <DialogContent className={classes.cardResponsive}>
          <DialogContentText>
            To add a device to LedFx, please first select the type of device you
            wish to add then provide the necessary configuration.
          </DialogContentText>
          <SchemaFormCollection
            schemaCollection={schemas.devices}
            onSubmit={this.handleSubmit}
            primaryFilter={prop => prop.required === true}
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

export default connect(mapStateToProps)(withStyles(styles)(DeviceConfigDialog));
