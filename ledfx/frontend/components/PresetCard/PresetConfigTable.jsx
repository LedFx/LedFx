import React from 'react';
import PropTypes from 'prop-types';
import { withStyles } from '@material-ui/core/styles';

import Table from '@material-ui/core/Table';
import TableHead from '@material-ui/core/TableHead';
import TableRow from '@material-ui/core/TableRow';
import TableCell from '@material-ui/core/TableCell';
import TableBody from '@material-ui/core/TableBody';

const styles = theme => ({
    table: {
      marginBottom: theme.spacing.unit * 4
    }
});

class DevicesTableItem extends React.Component {

  render() {
    const { classes, devices } = this.props;

    return (
        <Table className = { classes.table }>
          <TableHead>
            <TableRow>
              <TableCell>Device</TableCell>
              <TableCell>Effect</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {renderRows(devices)}
          </TableBody>
        </Table>
    );
  }
}

const renderRows = (devices) => {
  return Object.keys(devices).map((id) => {
    const device = devices[id]
    return (
      <TableRow key={id}>
          <TableCell>
              {id}
          </TableCell>
          <TableCell>
              {device.type}
          </TableCell>
      </TableRow>
  )
  })
}

DevicesTableItem.propTypes = {
  devices: PropTypes.object.isRequired
};

export default withStyles(styles)(DevicesTableItem);