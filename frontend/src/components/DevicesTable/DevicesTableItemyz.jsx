import React from 'react';
import { NavLink } from 'react-router-dom';
import { withStyles } from '@material-ui/core/styles';
import TableRow from '@material-ui/core/TableRow';
import TableCell from '@material-ui/core/TableCell';
import Button from '@material-ui/core/Button';
import DeleteIcon from '@material-ui/icons/Delete';
import EditIcon from '@material-ui/icons/Edit';
import ReorderIcon from '@material-ui/icons/Reorder';
import Slider from '@material-ui/core/Slider';

const styles = theme => ({
    button: {
        margin: 0,
        padding: 0,
        minWidth: 32,
    },
    deleteButton: {
        minWidth: 32,
    },
    editButton: {
        minWidth: 32,
    },
    actions: {
        display: 'flex',
        '& > *': {
            marginLeft: theme.spacing(1),
        },
    },
    deviceLink: {
        textDecoration: 'none',
        color: 'black',
        '&:hover': {
            color: theme.palette.primary.main,
        },
    },
});



function DevicesTableItem({ device, onDelete, classes, onEdit, index }) {
    const handleDeleteDevice = () => {
        onDelete(device.id);
    };

    const handleEditItem = () => {
        onEdit(device);
    };
    const [value, setValue] = React.useState([1, device.config.pixel_count]);

    const handleChange = (event, newValue) => {
        setValue(newValue);
    };
    const marks = [
        {
            value: 1,
            label: 1,
        },
        {
            value: device.config.pixel_count,
            label: device.config.pixel_count,
        },
    ];
    return (
        <TableRow key={device.id}>
            <TableCell style={{ width: '5%' }}>
                {index > -1 ? (
                    <span
                        style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                    >
                        {index + 1}
                        <ReorderIcon style={{ fontSize: 16 }} />
                    </span>
                ) : (
                        <span></span>
                    )}
            </TableCell>
            <TableCell style={{ width: '15%' }} component="th" scope="row">
                <NavLink
                    to={'/devices/' + device.id}
                    className={classes.deviceLink}
                    key={device.id}
                >
                    {device.config.name}
                </NavLink>
            </TableCell>
            <TableCell style={{ width: '13%' }}>{device.config.ip_address}</TableCell>
            <TableCell style={{ width: '10%' }}>{device.config.pixel_count}</TableCell>
            <TableCell style={{ width: '20%' }}>
                <Slider
                    value={value}
                    marks={marks}
                    min={1}
                    max={device.config.pixel_count}
                    onChange={handleChange}
                    valueLabelDisplay="auto"
                    aria-labelledby="range-slider"
                />
            </TableCell>


            <TableCell style={{ width: '10%' }} className={classes.actions}>
                <Button
                    color="secondary"
                    variant="contained"
                    size="small"
                    className={classes.deleteButton}
                    onClick={handleDeleteDevice}
                >
                    <DeleteIcon style={{ fontSize: 16 }} />
                </Button>
                <Button
                    variant="contained"
                    size="small"
                    className={classes.editButton}
                    onClick={handleEditItem}
                >
                    <EditIcon style={{ fontSize: 16 }} />
                </Button>
            </TableCell>
        </TableRow>
    );
}



export default withStyles(styles)(DevicesTableItem);
