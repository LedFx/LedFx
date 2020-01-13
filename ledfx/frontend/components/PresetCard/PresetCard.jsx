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
  card: {
    width: "100%",
    maxWidth: "100%",
    backgroundColor: "transparent",
    borderCollapse: "collapse",
  },
  deleteButton: {
    color: theme.palette.getContrastText(red[500]),
    backgroundColor: red[500],
    '&:hover': {
      backgroundColor: red[700],
    },
  },
});

class PresetCard extends React.Component {

  handleDeletePreset = presetId => {
    this.props.dispatch(deletePreset(presetId))
  }

  handleActivatePreset = presetId => {
    this.props.dispatch(activatePreset(presetId))
  }

  handleRenamePreset = presetId => {
    this.props.dispatch(RenamePreset(presetId, name))
  }

  render() {
    const { classes, preset } = this.props;

    return (
      <Card className={classes.card}>
        <CardContent>
          <h2>{preset.name}</h2>
          { preset.devices && <PresetConfigTable devices ={ preset.devices }/> }
        </CardContent>
        <CardActions>
          <Button
            color="primary"
            size="small"
            aria-label="Activate"
            variant = "contained"
            onClick={() => this.handleActivatePreset(preset.id)}
          >
            Activate
          </Button>
          <Button
            className={classes.deleteButton}
            size="small"
            aria-label="Delete"
            variant = "contained"
            onClick={() => this.handleDeletePreset(preset.id)}
          >
            Delete
          </Button> 
        </CardActions>
      </Card>
    );
  }
}

PresetConfigTable.propTypes = {
  classes: PropTypes.object.isRequired,
  preset: PropTypes.object.isRequired,
};

function mapStateToProps(state) {
  const { getPresets } = state

  return {
    getPresets
  }
}

export default  connect(mapStateToProps)(withStyles(styles)(PresetCard));