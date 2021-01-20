import React from 'react';
import PropTypes from 'prop-types';
import { NavLink } from 'react-router-dom';
import { withStyles } from '@material-ui/core/styles';
import TableRow from '@material-ui/core/TableRow';
import TableCell from '@material-ui/core/TableCell';
import Button from '@material-ui/core/Button';
import EditIcon from '@material-ui/icons/Edit';
import Icon from '@material-ui/core/Icon';
import { Link } from '@material-ui/core';
import PopoverSure from 'components/PopoverSure';

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

function DevicesTableItem({ device, onDelete, classes, onEdit, index, iconName }) {
    const handleDeleteDevice = () => {
        onDelete(device.id);
    };

    const handleEditItem = () => {
        onEdit(device);
    };
    const camel_to_snake = str =>
        str[0].toLowerCase() +
        str.slice(1, str.length).replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`);
    return (
        <TableRow key={device.id}>
            {/* {parseInt(window.localStorage.getItem('BladeMod')) >= 2 && ( */}
            <TableCell component="th" scope="row" width="35px">
                <Icon style={{ verticalAlign: 'bottom' }}>
                    {camel_to_snake(device.config.icon_name || 'SettingsInputComponent')}
                </Icon>
            </TableCell>
            {/* )} */}
            <TableCell>
                <NavLink
                    to={'/devices/' + device.id}
                    className={classes.deviceLink}
                    key={device.id}
                    color="inherit"
                >
                    {device.config.name}
                </NavLink>
            </TableCell>
            <TableCell>
                <Link color="inherit" target="_blank" href={`http://${device.config.ip_address}`}>
                    {device.config.ip_address}
                </Link>
            </TableCell>
            <TableCell>{device.config.pixel_count}</TableCell>
            <TableCell>{device.type}</TableCell>
            <TableCell align="right">
                <PopoverSure onConfirm={handleDeleteDevice} className={classes.deleteButton} />
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
