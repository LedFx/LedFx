import React from 'react';
import PropTypes from 'prop-types';
import Table from '@material-ui/core/Table';
import TableHead from '@material-ui/core/TableHead';
import TableRow from '@material-ui/core/TableRow';
import TableCell from '@material-ui/core/TableCell';
import TableBody from '@material-ui/core/TableBody';

const SceneConfigTable = ({ devices }) => (
    <Table>
        <TableHead>
            <TableRow>
                <TableCell>Device</TableCell>
                <TableCell>Effect</TableCell>
            </TableRow>
        </TableHead>
        <TableBody>{renderRows(devices)}</TableBody>
    </Table>
);

const renderRows = devices =>
    Object.keys(devices)
        .filter(id => !!devices[id].type)
        .map(id => (
            <TableRow key={id}>
                <TableCell>{id}</TableCell>
                <TableCell>{devices[id].type}</TableCell>
            </TableRow>
        ));

SceneConfigTable.propTypes = {
    classes: PropTypes.object.isRequired,
    devices: PropTypes.object.isRequired,
};

export default SceneConfigTable;
