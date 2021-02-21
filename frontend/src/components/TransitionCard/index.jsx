import React, { useEffect, useState } from 'react';
import { useSelector, useDispatch } from 'react-redux'
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
import FormControl from "@material-ui/core/FormControl";
import Select from "@material-ui/core/Select";
import MenuItem from "@material-ui/core/MenuItem";
import InputLabel from "@material-ui/core/InputLabel";
import Slider from "@material-ui/core/Slider";
import debounce from 'debounce';

// CONSTANT display categories
export const DEFAULT_CAT = 'default_presets';
export const CUSTOM_CAT = 'custom_presets';

const useStyles = makeStyles(theme => ({
    content: {
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'center',
        width: '100%',
        padding: theme.spacing(2),
        paddingBottom: 0,
    },
    actions: {
        display: 'flex',
        flexDirection: 'row',
        paddingBottom: theme.spacing(3),
    },
    formControl: {
        marginRight: theme.spacing(3),
    },
}));

const TransitionCard = ({ display, config, addDisplay }) => {
    const classes = useStyles();
    const dispatch = useDispatch();

    const schemas = useSelector(state => state.schemas.displays.schema.properties)
    const displays = useSelector(state => state.displays)
    console.log(displays)

    const transition_mode = display.config[display.id] && display.config[display.id].config && display.config[display.id].config.transition_mode
    const transition_time = display.config[display.id] && display.config[display.id].config && display.config[display.id].config.transition_time

    const handleSetTransition = (displayId, config) => () => {
        // useDispatch()
        console.log("Hello!")
        console.log(displayId, config)
        dispatch(addDisplay({ "id": displayId, "config": config }));
    };

    const debouncedOnChangeHandler = debounce(handleSetTransition, 200)

    const onChange = (e, newValue) => {
        debouncedOnChangeHandler(newValue);
    };

    const marks = [
        {
            value: schemas.transition_time.minimum,
            label: `${schemas.transition_time.minimum}s`
        },
        {
            value: schemas.transition_time.maximum,
            label: `${schemas.transition_time.maximum}s`
        },
    ]

    return (
        <Card variant="outlined">
            <CardHeader title="Transitions" subheader="Seamlessly blend between effects" />
            <CardContent className={classes.content}>
                <FormControl className={classes.formControl}>
                    <Typography variant="subtitle2">
                      Transition Duration
                    </Typography>
                    <Slider
                        defaultValue={schemas.transition_time.default}
                        // value={transitionTime}
                        onChange={onChange}
                        aria-labelledby="discrete-slider-always"
                        step={0.1}
                        marks={marks}
                        min={schemas.transition_time.minimum}
                        max={schemas.transition_time.maximum}
                        // disabled={type === "instant"}
                        valueLabelDisplay="auto"
                    />
                </FormControl>
                <FormControl className={classes.formControl}>
                    <InputLabel id="demo-simple-select-helper-label">Select a transition effect</InputLabel>
                    <Select onChange={handleSetTransition} >
                        {schemas.transition_mode.enum.map(mode => <MenuItem value={mode}>{mode}</MenuItem>)}
                    </Select>
                </FormControl>
            </CardContent>
        </Card>
    );
};

export default TransitionCard;
