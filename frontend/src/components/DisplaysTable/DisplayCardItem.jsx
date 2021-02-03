import React from 'react';
import Card from '@material-ui/core/Card';
import Wled from 'components/CustomIcons/Wled';
import { camelToSnake } from 'utils/helpers';
import Icon from '@material-ui/core/Icon';

import { NavLink } from 'react-router-dom';
import { withStyles } from '@material-ui/core/styles';

import Button from '@material-ui/core/Button';
import SettingsIcon from '@material-ui/icons/Settings';
import PopoverSure from 'components/PopoverSure';
import DisplaySegmentsDialog from 'components/DisplaySegmentsDialog';
import TuneIcon from '@material-ui/icons/Tune';
import BuildIcon from '@material-ui/icons/Build';

const styles = theme => ({
    deleteButton: {
        minWidth: 32,
    },
    editButton: {
        minWidth: 32,
        marginLeft: theme.spacing(1),
    },
    displayLink: {
        flexGrow: 1,
        padding: '0 0.5rem',
        textDecoration: 'none',
        fontSize: 'large',
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
    displayCard: {
        padding: '1rem',
        margin: '0.5rem',
        display: 'flex',
        alignItems: 'flex-start',
        flexDirection: 'column',
        '@media (max-width: 1200px)': {
            width: '100%',
        },
    },
});
const DisplayCardItem = ({
    display,
    classes,
    device,
    onDelete,
    onEditDevice,
    onEditDisplay,
    deviceList,
}) => {
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
        <Card className={classes.displayCard}>
            <div style={{ display: 'flex', alignItems: 'center', paddingBottom: '1rem' }}>
                <Icon
                    style={{ margingBottom: '4px', marginRight: '0.5rem' }}
                    color={display.effect && display.effect.active === true ? 'primary' : 'inherit'}
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
                <NavLink
                    to={'/displays/' + display.id}
                    className={classes.displayLink}
                    key={display.id}
                    color={display.effect && display.effect.active === true ? 'primary' : 'inherit'}
                >
                    {display.config.name}
                </NavLink>
            </div>
            <div>
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
            </div>
        </Card>
    );
};

export default withStyles(styles)(DisplayCardItem);
