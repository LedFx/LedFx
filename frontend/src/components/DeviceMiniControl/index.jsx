import React from 'react';
import PropTypes from 'prop-types';
import withStyles from '@material-ui/core/styles/withStyles';
import Grid from '@material-ui/core/Grid';
import Typography from '@material-ui/core/Typography';
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
    const {
        classes,
        device: { id, config, effect },
    } = props;

    return (
        <Grid container direction="row" spacing={1} justify="space-between">
            <Grid item xs="auto">
                <NavLink to={`/displays/${id}`} className={classes.textLink} key={id}>
                    <Typography variant="h5">{config.name}</Typography>
                </NavLink>
                <Typography variant="body1" color="textSecondary">
                    Effect: {effect.name ? effect.name : 'None'}
                </Typography>
            </Grid>
        </Grid>
    );
};

DeviceMiniControl.propTypes = {
    classes: PropTypes.object.isRequired,
    device: PropTypes.object.isRequired,
};

export default withStyles(styles)(DeviceMiniControl);
