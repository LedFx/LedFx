import React from 'react';
import PropTypes from 'prop-types';
import { connect } from 'react-redux'
import { withStyles } from '@material-ui/core/styles';
import Table from '@material-ui/core/Table';
import TableHead from '@material-ui/core/TableHead';
import TableRow from '@material-ui/core/TableRow';
import TableCell from '@material-ui/core/TableCell';
import TableBody from '@material-ui/core/TableBody';

import PresetsTableItem from 'frontend/components/DevicesTable/PresetsTableItem.jsx'
import { deletePreset } from 'frontend/actions'

const styles = theme => ({
  root: {
    width: '100%',
    maxWidth: 360,
    backgroundColor: theme.palette.background.paper,
  },
  nested: {
    paddingLeft: theme.spacing.unit * 4,
  }, 
  table: {
    marginBottom: "0",
    width: "100%",
    maxWidth: "100%",
    backgroundColor: "transparent",
    borderSpacing: "0",
    borderCollapse: "collapse"
  },
  tableResponsive: {
    width: "100%",
    overflowX: "auto"
  },
  tableCell: {
    lineHeight: "1.42857143",
    padding: "12px 8px",
    verticalAlign: "middle"
  }
});

class PresetsTable extends React.Component {

  handleDeletePreset = presetId => {
    this.props.dispatch(deletePreset(presetId))
  }

  handleSetPreset = presetId => {
    this.props.dispatch(setPreset(presetId))
  }

  render() {
    const { classes, devicesById } = this.props;

    return (
      <div className={classes.tableResponsive}>
      <Table className={classes.table}>
        <TableHead>
          <TableRow>
            <TableCell>Name</TableCell>
            <TableCell className={classes.tableCell}>Keyboard Key</TableCell>
            <TableCell className={classes.tableCell}>Keyboard Switch Type</TableCell>
            <TableCell className={classes.tableCell}>Trigger Spotify Song</TableCell>
            <TableCell className={classes.tableCell} numeric>Trigger Spotify Time(m:ss:ms)</TableCell>
            <TableCell className={classes.tableCell} numeric>Manage</TableCell>
          </TableRow>
        </TableHead>

        <TableBody>
          {
            Object.keys(devicesById).map(device_id => {
            return (
              <PevicesTableItem key={device_id} device={devicesById[device_id]} onDelete={this.handleDeletePreset}/>
            );
          })}
          {
            Object.keys(devicesById).map(device_id => {
            return (
              <PevicesTableItem key={device_id} device={devicesById[device_id]} onDelete={this.handleDeletePreset}/>
            );
          })}
        </TableBody>
      </Table>
      </div>
    );
  }
}

PresetsTable.propTypes = {
  classes: PropTypes.object.isRequired,
  devicesById: PropTypes.object.isRequired,
};

function mapStateToProps(state) {
  const { devicesById } = state

  return {
    devicesById
  }
}

export default  connect(mapStateToProps)(withStyles(styles)(PresetsTable));