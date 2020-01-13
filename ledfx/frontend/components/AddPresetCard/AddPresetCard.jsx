import React from 'react';
import PropTypes from 'prop-types';
import { connect } from 'react-redux'
import { withStyles } from '@material-ui/core/styles';

import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import CardActions from '@material-ui/core/CardActions';
import TextField from '@material-ui/core/TextField';
import Button from '@material-ui/core/Button';

import { addPreset } from 'frontend/actions';

const styles = theme => ({ 
  card: {
    display: "flex",
    direction: 'row',
    width: "100%",
    maxWidth: "100%",
    backgroundColor: "transparent",
    borderCollapse: "collapse",
    alignItems: 'center',
    justifyContent: 'space-between',
  },
});

class AddPresetCard extends React.Component {

  handleAddPreset = presetName => {
    this.props.dispatch(addPreset(presetName))
  }

  render() {
    const { classes } = this.props;

    return (
      <Card className={classes.card}>
        <CardContent>
          <h3>Add Preset</h3>
          <p>Save current effects of all devices as a preset</p>
        </CardContent>
        <CardActions>
          <form noValidate autoComplete="off">
            <TextField
              id="presetNameInput"
              label="Preset Name" 
            />
            <Button
              color="primary"
              size="small"
              aria-label="Save"
              variant = "contained"
              onClick={() => this.handleAddPreset(preset.name)}
            >
              Save
            </Button> 
          </form>
        </CardActions>
      </Card>
    );
  }
}

export default (withStyles(styles)(AddPresetCard));