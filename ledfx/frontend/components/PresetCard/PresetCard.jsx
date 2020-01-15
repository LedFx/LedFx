import React from 'react';
import PropTypes from 'prop-types';
import { connect } from 'react-redux'
import { withStyles } from '@material-ui/core/styles';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import CardActions from '@material-ui/core/CardActions';
import Button from '@material-ui/core/Button';
import red from '@material-ui/core/colors/red';

import PresetConfigTable from "frontend/components/PresetCard/PresetConfigTable";

import { activatePreset, deletePreset } from 'frontend/actions';

const styles = theme => ({ 
  deleteButton: {
    color: theme.palette.getContrastText(red[500]),
    backgroundColor: red[500],
    '&:hover': {
      backgroundColor: red[700],
    },
    margin: theme.spacing.unit,
    float: "right"
  },
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

class PresetCard extends React.Component {

  render() {
    const { classes, preset, activatePreset, deletePreset } = this.props;

    return (
      <Card>
        <CardContent>
          <h3>{preset.name}</h3>
          { preset.devices && <PresetConfigTable devices ={ preset.devices }/> }
        </CardContent>
        <CardActions className={classes.submitControls}>
            <Button
              className={classes.button}
              color="primary"
              size="small"
              aria-label="Activate"
              variant = "contained"
              onClick={() => activatePreset(preset.id)}
            >
              Activate
            </Button>
            <Button
              className={classes.deleteButton}
              color="red"
              size="small"
              aria-label="Delete"
              variant = "contained"
              onClick={() => deletePreset(preset.id)}
            >
              Delete
            </Button> 
          </CardActions>
      </Card>
    );
  }
}

PresetCard.propTypes = {
  classes: PropTypes.object.isRequired,
  preset: PropTypes.object.isRequired,
};

const mapDispatchToProps = (dispatch) => ({
  deletePreset: (presetId) => dispatch(deletePreset(presetId)),
  activatePreset: (presetId) => dispatch(activatePreset(presetId))
})

export default  connect(null , mapDispatchToProps)(withStyles(styles)(PresetCard));