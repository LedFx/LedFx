import React from 'react';
import PropTypes from 'prop-types';
import withStyles from '@material-ui/core/styles/withStyles';
import Button from '@material-ui/core/Button';
import Switch from '@material-ui/core/Switch';
import Grid from '@material-ui/core/Grid';
import Typography from '@material-ui/core/Typography';
import CircularProgress from '@material-ui/core/CircularProgress';
import { NavLink } from 'react-router-dom';

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
});

const DeviceMiniControl = props => {
    const toggleOn = ({ target: { checked } }) => {
        const { device, setDeviceEffect } = props;

        setDeviceEffect(device.id, {
            ...device.effect,
            active: checked,
        });
    };

    const {
        classes,
        device: { id, config, effect },
    } = props;

    return (
        <Grid container direction="row" spacing={1} justify="space-between">
            <Grid item xs="auto">
                <NavLink to={`/devices/${id}`} className={classes.textLink} key={id}>
                    <Typography variant="h5">{config.name}</Typography>
                </NavLink>
                <Typography variant="body1" color="textSecondary">
                    Effect: {effect.name ? effect.name : 'None'}
                </Typography>
            </Grid>

            <Grid item className={classes.actionsContainer}>
                <Button
                    component={NavLink}
                    to={`/devices/${id}`}
                    className={classes.deviceLink}
                    key={id}
                >
                    Change Effect
                </Button>
                <Grid
                    container
                    justify="center"
                    alignContent="center"
                    className={classes.toggleContainer}
                >
                    {effect.isProcessing ? (
                        <CircularProgress size={20} />
                    ) : (
                        <Switch checked={effect.active} onChange={toggleOn} color="primary" />
                    )}
                </Grid>
            </Grid>
        </Grid>
    );
};

DeviceMiniControl.propTypes = {
    classes: PropTypes.object.isRequired,
    device: PropTypes.object.isRequired,
    setDeviceEffect: PropTypes.func.isRequired,
};

export default withStyles(styles)(DeviceMiniControl);
