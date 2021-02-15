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
        padding: '3px 5px',
        marginLeft: '0.5rem',
        flexGrow: 0,
    },
    previewButton: {
        height: '16px',
        fontSize: '12px',
        minWidth: 'unset',
        padding: '2px 4px',
        marginLeft: '0.5rem',
        flexGrow: 0,
    },
    displayLink: {
        flexGrow: 0,
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
    displayCardPortrait: {
        padding: '1rem',
        margin: '0.5rem',
        display: 'flex',
        alignItems: 'flex-start',
        flexDirection: 'column',
        minWidth: '180px',
        height: '240px',
    },
    displayIcon: {
        margingBottom: '4px',
        marginRight: '0.5rem',
        position: 'relative',
        fontSize: '50px',
    },
    displayCardContainer: {
        display: 'flex',
        alignItems: 'center',
        flexDirection: 'column',
        width: '100%',
        height: '100%',
        justifyContent: 'space-between',
    }
});
const DisplayCardItemPortrait = ({
    display,
    classes,
    variant = 'outlined',
    color = "default",
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
        <Card className={classes.displayCardPortrait}>
            <div
                className={classes.displayCardContainer}
            >
                <Icon
                    color={display.effect && display.effect.active === true ? 'primary' : 'inherit'}
                    className={classes.displayIcon}
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


                <div>
                    <Button variant={variant} disabled size="small" className={classes.badgeButton}>
                        {(deviceList.find(d => d.id === display.is_device) &&
                            deviceList.find(d => d.id === display.is_device).type) || 'VIRTUAL'}
                    </Button>

                    {display.config.preview_only && (
                        <Button
                            variant={'text'}
                            disabled
                            size="small"

                            className={classes.previewButton}
                        >
                            <VisibilityIcon />
                        </Button>
                    )}
                </div>
                <div>
                    <PopoverSure
                        variant={variant}
                        color={color}
                        onConfirm={handleDeleteDevice}
                        className={classes.deleteButton}
                    />

                    {display.is_device ? (
                        <Button
                            variant={variant}
                            color={color}
                            size="small"
                            className={classes.editButton}
                            onClick={handleEditDevice}
                        >
                            <BuildIcon />
                        </Button>
                    ) : (
                            <DisplaySegmentsDialog
                                variant={variant}
                                color={color}
                                display={display}
                                className={classes.editButton}
                                icon={<TuneIcon />}
                            />
                        )}
                    <Button
                        variant={variant}
                        size="small"
                        color={color}
                        className={classes.editButton}
                        onClick={handleEditDisplay}
                    >
                        <SettingsIcon />
                    </Button>
                </div>
            </div>
        </Card>
    );
};

export default withStyles(styles)(DisplayCardItemPortrait);
