import React from 'react';
import PropTypes from 'prop-types';
import { withStyles } from '@material-ui/core/styles';
import Table from '@material-ui/core/Table';
import TableHead from '@material-ui/core/TableHead';
import TableRow from '@material-ui/core/TableRow';
import TableCell from '@material-ui/core/TableCell';
import TableBody from '@material-ui/core/TableBody';

import DevicesTableItem from './DevicesTableItem.jsx';

const styles = theme => ({
    table: {
        borderSpacing: '0',
        borderCollapse: 'collapse',
    },
    tableResponsive: {
        overflowX: 'auto',
    },
});

function DevicesTable({ onDeleteDevice, classes, items, onEditDevice }) {
    return (
        <div className={classes.tableResponsive}>
            <Table className={classes.table}>
                <TableHead>
                    <TableRow>
                        <TableCell style={{ width: '5%' }} />
                        <TableCell style={{ width: '25%' }}>Name</TableCell>
                        <TableCell style={{ width: '20%' }}>IP Address</TableCell>
                        <TableCell style={{ width: '15%' }}>Pixel Count</TableCell>
                        <TableCell style={{ width: '15%' }}>Type</TableCell>
                        <TableCell style={{ width: '10%' }} align="right" />
                    </TableRow>
                </TableHead>
                {/* 
                <TableBody>
                    {items.map(device => {
                        return (
                            <DevicesTableItem
                                key={device.id}
                                device={device}
                                onDelete={onDeleteDevice}
                                onEdit={onEditDevice}
                            />
                        );
                    })}
                </TableBody> */}
            </Table>
        </div>
    );
}

DevicesTable.propTypes = {
    classes: PropTypes.object.isRequired,
    items: PropTypes.array.isRequired,
};

export default withStyles(styles)(DevicesTable);
