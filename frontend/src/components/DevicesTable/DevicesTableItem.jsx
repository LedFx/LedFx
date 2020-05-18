import React from 'react';
import PropTypes from 'prop-types';
import { NavLink } from 'react-router-dom';

import { withStyles } from '@material-ui/core/styles';
import TableRow from '@material-ui/core/TableRow';
import TableCell from '@material-ui/core/TableCell';
import Button from '@material-ui/core/Button';
import DeleteIcon from '@material-ui/icons/Delete';
import red from '@material-ui/core/colors/red';

const styles = theme => ({
    tableCell: {
        lineHeight: '1.42857143',
        padding: '12px 8px',
        verticalAlign: 'middle',
    },
    button: {
        margin: 0,
        padding: 0,
        minWidth: 32,
    },
    deleteButton: {
        minWidth: 32,
        color: theme.palette.getContrastText(red[500]),
        backgroundColor: red[500],
        '&:hover': {
            backgroundColor: red[700],
        },
    },
    deviceLink: {
        textDecoration: 'none',
        '&,&:hover': {
            color: '#000000',
        },
    },
});

class DevicesTableItem extends React.Component {
    handleDeleteDevice = () => {
        this.props.onDelete(this.props.device.id);
    };

    render() {
        const { classes, device } = this.props;
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
                <TableCell className={classes.tableCell}>{device.config.ip_address}</TableCell>
                <TableCell className={classes.tableCell}>{device.config.pixel_count}</TableCell>
                <TableCell className={classes.tableCell}>{device.type}</TableCell>
                <TableCell className={classes.tableCell} numeric>
                    <Button
                        variant="contained"
                        size="small"
                        className={classes.deleteButton}
                        onClick={this.handleDeleteDevice}
                    >
                        <DeleteIcon style={{ fontSize: 16 }} />
                    </Button>
                </TableCell>
            </TableRow>
        );
    }
}

DevicesTableItem.propTypes = {
    classes: PropTypes.object.isRequired,
    device: PropTypes.object.isRequired,
    onDelete: PropTypes.func.isRequired,
};

export default withStyles(styles)(DevicesTableItem);
