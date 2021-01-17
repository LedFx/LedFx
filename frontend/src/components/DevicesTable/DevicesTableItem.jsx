import React from 'react';
import PropTypes from 'prop-types';
import { NavLink } from 'react-router-dom';
import { withStyles } from '@material-ui/core/styles';
import TableRow from '@material-ui/core/TableRow';
import TableCell from '@material-ui/core/TableCell';
import Button from '@material-ui/core/Button';
import DeleteIcon from '@material-ui/icons/Delete';
import EditIcon from '@material-ui/icons/Edit';

const styles = theme => ({
    deleteButton: {
        minWidth: 32,
    },
    editButton: {
        minWidth: 32,
        marginLeft: theme.spacing(1),
    },
    deviceLink: {
        textDecoration: 'none',
        color: 'inherit',
        '&:hover': {
            color: theme.palette.primary.main,
        },
    },
});

function DevicesTableItem({ device, onDelete, classes, onEdit, index }) {
    const handleDeleteDevice = () => {
        onDelete(device.id);
        window.location = window.location.href;
    };

    const handleEditItem = () => {
        onEdit(device);
    };

    return (
        <TableRow key={device.id}>
            <TableCell component="th" scope="row">
                <NavLink
                    to={'/devices/' + device.id}
                    className={classes.deviceLink}
                    key={device.id}
                >
                    {device.config.name}
                </NavLink>
            </TableCell>
            <TableCell>{device.config.ip_address}</TableCell>
            <TableCell>{device.config.pixel_count}</TableCell>
            <TableCell>{device.type}</TableCell>
            <TableCell align="right">
                <Button
                    color="secondary"
                    variant="contained"
                    size="small"
                    className={classes.deleteButton}
                    onClick={handleDeleteDevice}
                >
                    <DeleteIcon />
                </Button>
                <Button
                    variant="contained"
                    size="small"
                    className={classes.editButton}
                    onClick={handleEditItem}
                >
                    <EditIcon />
                </Button>
            </TableCell>
        </TableRow>
    );
}

DevicesTableItem.propTypes = {
    classes: PropTypes.object.isRequired,
    device: PropTypes.object.isRequired,
    onDelete: PropTypes.func.isRequired,
};

export default withStyles(styles)(DevicesTableItem);
