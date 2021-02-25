import React from 'react';
import { useSelector, useDispatch } from 'react-redux'
import PropTypes from 'prop-types';
import withStyles from '@material-ui/core/styles/withStyles';
import Grid from '@material-ui/core/Grid';
import Typography from '@material-ui/core/Typography';
import { NavLink } from 'react-router-dom';
import Wled from 'components/CustomIcons/Wled';
import { camelToSnake } from 'utils/helpers';
import Icon from '@material-ui/core/Icon';
import { Button } from '@material-ui/core';
import { Pause, PlayArrow, Stop } from '@material-ui/icons';
import { clearDisplayEffect, toggleDisplay } from 'modules/displays';

const styles = theme => ({
    button: {
        margin: theme.spacing(1),
        float: 'right',
    },
    submitControls: {
        margin: theme.spacing(1),
        display: 'block',
        width: '100%',
    },
    tableCell: {
        lineHeight: '1.2',
        padding: '12px 8px',
        verticalAlign: 'middle',
    },
    deviceLink: {
        size: 'large',
        margin: theme.spacing(1),
        textDecoration: 'none',
        '&,&:hover': {
            color: 'inherit',
        },
    },
    textLink: {
        textDecoration: 'none',
        color: 'inherit',
        '&:hover': {
            color: theme.palette.primary.main,
        },
    },
    actionsContainer: {
        display: 'flex',
        justifyContent: 'flex-end',
    },
    toggleContainer: {
        width: '70px',
    },
    displayIcon: {
        margin: '0rem 1rem',
        position: 'relative',
        fontSize: '50px',
    },
    actionButtonsWrapper: {
        marginRight: '9px'
    }
});

const DeviceMiniControl = props => {
    const {
        classes,
        device: { id, config, effect, active }
    } = props;
    const devices = useSelector(state => state.devices.list)
    const displays = useSelector(state => state.displays.list)
    const dev = devices.find(d => d.id === id)
    const stream = dev && dev.active_displays
    const dispatch = useDispatch();
    if (effect) {
        return (
            <Grid container direction="row" spacing={1} justify="space-between">
                <Grid item xs="auto" style={{ width: "100%" }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', margin: '0.5rem 0' }}>
                        <div style={{ display: 'flex', alignItems: 'flex-start', margin: '0.5rem 0' }}>
                            <Icon
                                color={effect && effect.active === true ? 'primary' : 'inherit'}
                                className={classes.displayIcon}
                            >
                                {config.icon_name && config.icon_name.startsWith('wled') ? (
                                    <Wled />
                                ) : config.icon_name.startsWith('mdi:') ? (
                                    <span
                                        className={`mdi mdi-${config.icon_name.split('mdi:')[1]}`}
                                    ></span>
                                ) : (
                                            camelToSnake(config.icon_name || 'SettingsInputComponent')
                                        )}
                            </Icon>
                            <div>
                                <NavLink to={`/displays/${id}`} className={classes.textLink} key={id}>
                                    <Typography variant="h5">{config.name}</Typography>
                                </NavLink>
                                {effect.name ? (
                                    <Typography variant="body1" color="textSecondary">
                                        Effect: {effect.name}
                                    </Typography>
                                ) : (<></>)}
                                {!effect.name && stream && stream.length > 0 ? (<Typography variant="body1" color="textSecondary">
                                    Streaming from: {stream.map(s => displays.find(dis => dis.id === s).name).join(',')}
                                </Typography>) : (<></>)}
                            </div>
                        </div>
                        {effect.name && (
                            <div className={classes.actionButtonsWrapper}>
                                <Button disabled={stream && stream.length > 0 && !effect.name} variant="outlined" style={{ marginRight: '0.5rem' }} onClick={() => {

                                    dispatch(clearDisplayEffect(id))
                                }}>
                                    <Stop />
                                </Button>
                                <Button disabled={stream && stream.length > 0 && !effect.name} variant="outlined" onClick={() => {
                                    active
                                        ? dispatch(toggleDisplay(id, { active: false }))
                                        : dispatch(toggleDisplay(id, { active: true }))
                                }}>
                                    {active ? (<Pause />) : (<PlayArrow />)}
                                </Button>
                            </div>
                        )}
                    </div>

                </Grid>

            </Grid>
        );
    }
};

DeviceMiniControl.propTypes = {
    classes: PropTypes.object.isRequired,
    device: PropTypes.object.isRequired,
};

export default withStyles(styles)(DeviceMiniControl);
