import React from 'react';
import PropTypes from 'prop-types';
import { NavLink } from 'react-router-dom';
import { withStyles } from '@material-ui/core/styles';
import TableRow from '@material-ui/core/TableRow';
import TableCell from '@material-ui/core/TableCell';
import Button from '@material-ui/core/Button';
import EditIcon from '@material-ui/icons/Edit';
import Icon from '@material-ui/core/Icon';
import { Link, Switch } from '@material-ui/core';
import PopoverSure from 'components/PopoverSure';
import { camelToSnake } from 'utils/helpers';
const styles = theme => ({
    deleteButton: {
        minWidth: 32,
    },
    editButton: {
        minWidth: 32,
        marginLeft: theme.spacing(1),
    },
    displayLink: {
        textDecoration: 'none',
        color: 'inherit',
        '&:hover': {
            color: theme.palette.primary.main,
        },
    },
});

function DevicesTableItem({ display, onDelete, classes, onEdit }) {
    const handleDeleteDevice = () => {
        onDelete(display.id);
    };

    const handleEditItem = () => {
        onEdit(display);
    };

    return (
        <TableRow key={display.id}>
            <TableCell component="th" scope="row" width="35px">
                <Icon style={{ verticalAlign: 'bottom' }}>
                    {camelToSnake(display.config.icon_name || 'SettingsInputComponent')}
                </Icon>
            </TableCell>
            <TableCell>
                <NavLink
                    to={'/displays/' + display.id}
                    className={classes.displayLink}
                    key={display.id}
                    color="inherit"
                >
                    {display.config.name}
                </NavLink>
            </TableCell>
            <TableCell>{display.config.max_brightness}</TableCell>
            <TableCell>{display.config.crossfade}</TableCell>
            <TableCell>{display.config.center_offset}</TableCell>
            <TableCell>
                <Switch checked={display.config.preview_only} />
            </TableCell>
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
    display: PropTypes.object.isRequired,
    onDelete: PropTypes.func.isRequired,
};

export default withStyles(styles)(DevicesTableItem);
