import React from 'react';
import PropTypes from 'prop-types';
import { withStyles } from '@material-ui/core/styles';
import ListSubheader from '@material-ui/core/ListSubheader';
import Table from '@material-ui/core/Table';
import TableHead from '@material-ui/core/TableHead';
import TableRow from '@material-ui/core/TableRow';
import TableCell from '@material-ui/core/TableCell';
import TableBody from '@material-ui/core/TableBody';
import Typography from '@material-ui/core/Typography';
import DraftsIcon from '@material-ui/icons/Drafts';
import SendIcon from '@material-ui/icons/Send';
import ExpandLess from '@material-ui/icons/ExpandLess';
import ExpandMore from '@material-ui/icons/ExpandMore';
import StarBorder from '@material-ui/icons/StarBorder';

import DevicesTableItem from 'frontend/components/DevicesTable/DevicesTableItem.jsx'

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

class DevicesTable extends React.Component {

  render() {
    const { classes, devices } = this.props;

    return (
      <div className={classes.tableResponsive}>
      <Table className={classes.table}>
        <TableHead>
          <TableRow>
            <TableCell>Name</TableCell>
            <TableCell className={classes.tableCell}>Type</TableCell>
            <TableCell className={classes.tableCell} numeric>Manage</TableCell>
          </TableRow>
        </TableHead>

        <TableBody>
          {devices.map(device => {
            return (
              <DevicesTableItem device={device}/>
            );
          })}
        </TableBody>
      </Table>
      </div>
    );
  }
}

DevicesTable.propTypes = {
  classes: PropTypes.object.isRequired,
};

export default withStyles(styles)(DevicesTable);