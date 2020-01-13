import React from 'react';
import PropTypes from 'prop-types';
import { connect } from 'react-redux'
import { withStyles } from '@material-ui/core/styles';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import Button from '@material-ui/core/Button';

import PresetConfigTable from "frontend/components/PresetCard/PresetConfigTable";
import PresetsConfigDialog from "frontend/components/PresetConfigDialog/PresetConfigDialog";

import { activatePreset, deletePreset } from 'frontend/actions';

const styles = theme => ({ 
  card: {
    marginBottom: "0",
    width: "100%",
    maxWidth: "100%",
    backgroundColor: "transparent",
    borderSpacing: "0",
    borderCollapse: "collapse"
  },
});

class PresetCard extends React.Component {

  handleDeletePreset = presetId => {
    this.props.dispatch(deletePreset(presetId))
  }

  handleActivatePreset = presetId => {
    this.props.dispatch(activatePreset(presetId))
  }

  render() {
    const { classes, preset } = this.props;

    return (
      <Card className={classes.card}>
        <CardContent>
          <h3>{preset.name}</h3>
          { preset.devices && <PresetConfigTable devices ={ preset.devices }/> }
          <Button
            color="primary"
            size="small"
            aria-label="Activate"
            variant = "contained"
            onClick={() => this.handleActivatePreset(preset.id)}
          >
            Activate
          </Button> 
        </CardContent>
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