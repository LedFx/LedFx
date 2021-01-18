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
        size: "large",
        margin: theme.spacing(1),
        textDecoration: "none",
        "&,&:hover": {
          color: "#000000"
        },
    },
    actionsContainer: {
        display: 'flex',
        justifyContent: 'flex-end'
    },
    toggleContainer: {
        width: '70px',
    },
});

class DeviceMiniControl extends React.Component {
    toggleOn = ({ target: { checked } }) => {
        const { device, setDeviceEffect } = this.props;

        setDeviceEffect(device.id, {
            ...device.effect,
            active: checked,
        });
    };

    render() {
        const {
            classes,
            device: { id, config, effect },
        } = this.props;

        return (
            <Grid container direction="row" spacing={1} justify="space-between">
                <Grid item xs="auto">
                    <Typography variant="h5">
                        {config.name}
                    </Typography>
                    <Typography variant="body1" color="textSecondary">
                        Effect: {effect.name ? effect.name : "None"}
                    </Typography>
                </Grid>

                <Grid
                    item
                    className={classes.actionsContainer}
                >
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
                            <Switch
                                checked={effect.active}
                                onChange={this.toggleOn}
                                color="primary"
                            />
                        )}
                    </Grid>
                </Grid>
            </Grid>
        );
    }
}

DeviceMiniControl.propTypes = {
    classes: PropTypes.object.isRequired,
    device: PropTypes.object.isRequired,
    setDeviceEffect: PropTypes.func.isRequired,
};

export default withStyles(styles)(DeviceMiniControl);
