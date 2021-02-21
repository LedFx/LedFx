import React, { useEffect, useState } from 'react';
import { useDispatch } from 'react-redux'
import { makeStyles } from '@material-ui/core/styles';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import CardActions from '@material-ui/core/CardActions';
import CardHeader from '@material-ui/core/CardHeader';
import Button from '@material-ui/core/Button';
import Grid from '@material-ui/core/Grid';
import Typography from '@material-ui/core/Typography';
import TextField from '@material-ui/core/TextField';
import SaveIcon from '@material-ui/icons/Save';
import { addDisplay } from 'modules/displays'

// CONSTANT display categories
export const DEFAULT_CAT = 'default_presets';
export const CUSTOM_CAT = 'custom_presets';

const useStyles = makeStyles(theme => ({
    content: {
        display: 'flex',
        flexDirection: 'column',
        width: '100%',
        padding: theme.spacing(2),
        paddingBottom: 0,
    },
    actions: {
        display: 'flex',
        flexDirection: 'row',
        paddingBottom: theme.spacing(3),
    },
}));

const TransitionCard = ({ display, config, addDisplay }) => {
    const classes = useStyles();
    const dispatch = useDispatch();

    const handleSetTransition = (displayId, config) => () => {
        dispatch(addDisplay({"id": displayId, "config": config}));
    };

    return (
        <Card variant="outlined">
            <CardHeader title="Transitions" subheader="Seamlessly blend between effects" />
            <CardContent className={classes.content}>
                <Typography variant="body1" color="textSecondary">
                    Save this effect configuration as a preset
                </Typography>
            </CardContent>
        </Card>
    );
};

export default TransitionCard;
