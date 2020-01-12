import React from 'react';
import PropTypes from 'prop-types';
import { connect } from 'react-redux'
import { withStyles } from '@material-ui/core/styles';
import Table from '@material-ui/core/Table';
import TableHead from '@material-ui/core/TableHead';
import TableRow from '@material-ui/core/TableRow';
import TableCell from '@material-ui/core/TableCell';
import TableBody from '@material-ui/core/TableBody';

import PresetConfigTable from "frontend/components/PresetCard/PresetConfigTable.jsx";
import { deletePreset } from 'frontend/actions';
import { setPreset } from 'frontend/actions';

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

  handleSetPreset = presetId => {
    this.props.dispatch(setPreset(presetId))
  }

  render() {
    const { classes, preset } = this.props;

    return (
      <div>
      <Card className={classes.card}>
        <CardContent>
          <h1>{preset['name']}</h1>
          <PresetConfigTable key={preset_id} config={preset['devices']}/>
          <Button
            variant="fab"
            color="primary"
            aria-label="Add"
            className={classes.button}
            onClick={this.openAddDeviceDialog}
          >
          <AddIcon />
          </Button>
          <PresetsConfigDialog
            open={this.state.addDialogOpened}
            onClose={this.closeAddDeviceDialog}
          />
        </CardContent>
      </Card>
      </div>
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

export default  connect(mapStateToProps)(withStyles(styles)(PresetConfigTable));