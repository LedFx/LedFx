import React from 'react';
import Card from '@material-ui/core/Card';
import Wled from 'components/CustomIcons/Wled';
import { camelToSnake } from 'utils/helpers';
import Icon from '@material-ui/core/Icon';

import { NavLink } from 'react-router-dom';
import { withStyles } from '@material-ui/core/styles';

import Button from '@material-ui/core/Button';
// import Badge from '@material-ui/core/Badge';
import SettingsIcon from '@material-ui/icons/Settings';
import PopoverSure from 'components/PopoverSure';
import DisplaySegmentsDialog from 'components/DisplaySegmentsDialog';
import TuneIcon from '@material-ui/icons/Tune';
import VisibilityIcon from '@material-ui/icons/Visibility';
import BuildIcon from '@material-ui/icons/Build';

const styles = theme => ({
    deleteButton: {
        minWidth: 32,
    },
    editButton: {
        minWidth: 32,
        marginLeft: theme.spacing(1),
    },
    badgeButton: {
        height: '16px',
        fontSize: '12px',
        minWidth: 'unset',
        padding: '2px 4px',
        marginLeft: '0.5rem',
        flexGrow: 0,
    },
    displayLink: {
        flexGrow: 1,
        padding: '0 0.5rem',
        textDecoration: 'none',
        fontSize: 'large',
        color: 'inherit',
        whiteSpace: 'nowrap',
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
        minWidth: '400px',
        '@media (max-width: 1123px)': {
            width: '100%',
            minWidth: 'unset',
            marginBottom: '0.5rem',
        },
    },
    actionButtons: {
        display: 'flex',
        '@media (max-width: 420px)': {
            flexDirection: 'column',
            alignItems: 'flex-end',
        },
    },
});
const DisplayCardItem = ({
    display,
    classes,
    variant = 'outlined',
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
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    // paddingBottom: '1rem',
                    width: '100%',
                }}
            >
                <Icon
                    color={display.effect && display.effect.active === true ? 'primary' : 'inherit'}
                    style={{ margingBottom: '4px', marginRight: '0.5rem', position: 'relative' }}
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
                <div
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        flexGrow: 1,
                    }}
                >
                    <div
                        style={{
                            display: 'flex',
                            flexDirection: 'column',
                        }}
                    >
                        <NavLink
                            to={'/displays/' + display.id}
                            className={classes.displayLink}
                            key={display.id}
                            color={
                                display.effect && display.effect.active === true
                                    ? 'primary'
                                    : 'inherit'
                            }
                        >
                            {display.config.name}
                        </NavLink>

                        <div>
                            {/* {deviceList.find(d => d.id === display.is_device) &&
                            deviceList.find(d => d.id === display.is_device).type === 'udp' ? (
                                <Button
                                    variant={variant}
                                    color="secondary"
                                    size="small"
                                    className={classes.badgeButton}
                                >
                                    <Badge badgeContent={'!'} color="primary">
                                        UDP{' '}
                                    </Badge>
                                </Button>
                            ) : ( */}
                            <Button
                                variant={variant}
                                disabled
                                size="small"
                                className={classes.badgeButton}
                            >
                                {deviceList.find(d => d.id === display.is_device) &&
                                    deviceList.find(d => d.id === display.is_device).type}
                            </Button>
                            {display.config.preview_only && (
                                <Button
                                    variant={'text'}
                                    disabled
                                    size="small"
                                    className={classes.badgeButton}
                                >
                                    <VisibilityIcon />
                                </Button>
                            )}
                            {/* )} */}
                        </div>
                    </div>
                    {/* <div>
                        {deviceList.find(d => d.id === display.is_device) &&
                        deviceList.find(d => d.id === display.is_device).type === 'udp' ? (
                            <Button
                                variant={variant}
                                color="secondary"
                                size="small"
                                className={classes.editButton}
                            >
                                <Badge badgeContent={'!'} color="primary">
                                    UDP{' '}
                                </Badge>
                            </Button>
                        ) : (
                            <Button
                                variant={variant}
                                disabled
                                size="small"
                                className={classes.editButton}
                            >
                                {deviceList.find(d => d.id === display.is_device) &&
                                    deviceList.find(d => d.id === display.is_device).type}
                            </Button>
                        )}
                        {display.config.preview_only && (
                            <Button
                                variant={variant}
                                disabled
                                size="small"
                                className={classes.editButton}
                            >
                                <VisibilityIcon />
                            </Button>
                        )}
                    </div> */}
                    <div className={classes.actionButtons}>
                        <PopoverSure
                            variant={variant}
                            onConfirm={handleDeleteDevice}
                            className={classes.deleteButton}
                        />

                        {display.is_device ? (
                            <Button
                                variant={variant}
                                size="small"
                                className={classes.editButton}
                                onClick={handleEditDevice}
                            >
                                <BuildIcon />
                            </Button>
                        ) : (
                            <DisplaySegmentsDialog
                                variant={variant}
                                display={display}
                                className={classes.editButton}
                                icon={<TuneIcon />}
                            />
                        )}
                        <Button
                            variant={variant}
                            size="small"
                            className={classes.editButton}
                            onClick={handleEditDisplay}
                        >
                            <SettingsIcon />
                        </Button>
                    </div>
                </div>
            </div>
            {/* <div>
                <PopoverSure
                    variant={variant}
                    onConfirm={handleDeleteDevice}
                    className={classes.deleteButton}
                />

                {display.is_device ? (
                    <Button
                        variant={variant}
                        size="small"
                        className={classes.editButton}
                        onClick={handleEditDevice}
                    >
                        <BuildIcon />
                    </Button>
                ) : (
                    <DisplaySegmentsDialog
                        variant={variant}
                        display={display}
                        className={classes.editButton}
                        icon={<TuneIcon />}
                    />
                )}
                <Button
                    variant={variant}
                    size="small"
                    className={classes.editButton}
                    onClick={handleEditDisplay}
                >
                    <SettingsIcon />
                </Button>
            </div> */}
        </Card>
    );
};

export default withStyles(styles)(DisplayCardItem);
