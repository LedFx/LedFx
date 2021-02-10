import React from 'react';
import PropTypes from 'prop-types';
import { NavLink } from 'react-router-dom';
import { withStyles } from '@material-ui/core/styles';
import TableRow from '@material-ui/core/TableRow';
import TableCell from '@material-ui/core/TableCell';
import Button from '@material-ui/core/Button';
import SettingsIcon from '@material-ui/icons/Settings';
import Icon from '@material-ui/core/Icon';
import PopoverSure from 'components/PopoverSure';
import DisplaySegmentsDialog from 'components/DisplaySegmentsDialog';
import { camelToSnake } from 'utils/helpers';
import TuneIcon from '@material-ui/icons/Tune';
import BuildIcon from '@material-ui/icons/Build';
import Wled from 'components/CustomIcons/Wled';
import DoneIcon from '@material-ui/icons/Done';
import ClearIcon from '@material-ui/icons/Clear';

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
    displaySettings: {
        '@media (max-width: 1200px)': {
            display: 'none',
        },
    },
});

function DisplaysTableItem({
    display,
    device,
    onDelete,
    classes,
    onEditDevice,
    onEditDisplay,
    deviceList,
}) {
    const handleDeleteDevice = () => {
        onDelete(display.id);
    };

    const handleEditDisplay = () => {
        onEditDisplay(display);
    };
    const handleEditDevice = () => {
        onEditDevice(deviceList.find(d => d.id === display.is_device));
    };

    return (
        <TableRow key={display.id}>
            <TableCell component="th" scope="row" width="35px">
                <Icon
                    color={display.effect && display.effect.active === true ? 'primary' : 'inherit'}
                    style={{ position: 'relative' }}
                >
                    {display.config.icon_name && display.config.icon_name.startsWith('wled') ? (
                        <Wled />
                    ) : display.config.icon_name.startsWith('mdi:') ? (
                        <span
                            className={`mdi mdi-${display.config.icon_name.split('mdi:')[1]}`}
                        ></span>
                    ) : (
                        camelToSnake(display.config.icon_name || 'SettingsInputComponent')
                    )}
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
            <TableCell className={classes.displaySettings}>
                {display.config.max_brightness * 100 + '%'}
            </TableCell>
            <TableCell className={classes.displaySettings}>{display.config.crossfade}</TableCell>
            <TableCell align="center" className={classes.displaySettings}>
                {display.config.center_offset}
            </TableCell>
            <TableCell valign="bottom" className={classes.displaySettings}>
                {display.config.preview_only ? <DoneIcon /> : <ClearIcon />}
            </TableCell>
            <TableCell align="right" valign="bottom">
                <PopoverSure onConfirm={handleDeleteDevice} className={classes.deleteButton} />

                {display.is_device ? (
                    <Button
                        variant="contained"
                        size="small"
                        className={classes.editButton}
                        onClick={handleEditDevice}
                    >
                        <BuildIcon />
                    </Button>
                ) : (
                    <DisplaySegmentsDialog
                        display={display}
                        className={classes.editButton}
                        icon={<TuneIcon />}
                    />
                )}
                <Button
                    variant="contained"
                    size="small"
                    className={classes.editButton}
                    onClick={handleEditDisplay}
                >
                    <SettingsIcon />
                </Button>
            </TableCell>
        </TableRow>
    );
}

DisplaysTableItem.propTypes = {
    classes: PropTypes.object.isRequired,
    display: PropTypes.object.isRequired,
    onDelete: PropTypes.func.isRequired,
};

export default withStyles(styles)(DisplaysTableItem);
