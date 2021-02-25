import React from 'react';
import { useSelector } from 'react-redux';
import PropTypes from 'prop-types';
import Table from '@material-ui/core/Table';
import TableHead from '@material-ui/core/TableHead';
import TableRow from '@material-ui/core/TableRow';
import TableCell from '@material-ui/core/TableCell';
import TableBody from '@material-ui/core/TableBody';

const SceneConfigTable = ({ displays }) => {
    const displayList = useSelector(state => state.displays.list)
    return (
        <Table>
            <TableHead>
                <TableRow>
                    <TableCell>Device</TableCell>
                    <TableCell>Effect</TableCell>
                </TableRow>
            </TableHead>
            <TableBody>{renderRows(displays, displayList)}</TableBody>
        </Table>
    )
};

const renderRows = (displays, displayList) =>
    Object.keys(displays)
        .filter(id => !!displays[id].type)
        .map(id => (
            <TableRow key={id}>
                <TableCell>{displayList.find(d => d.id === id) && displayList.find(d => d.id === id).name}</TableCell>
                <TableCell>{displays[id].type}</TableCell>
            </TableRow>
        ));

SceneConfigTable.propTypes = {
    classes: PropTypes.object.isRequired,
    displays: PropTypes.object.isRequired,
};

export default SceneConfigTable;
