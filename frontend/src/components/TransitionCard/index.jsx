import React from 'react';
import { useSelector, useDispatch } from 'react-redux'
import { makeStyles } from '@material-ui/core/styles';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import CardHeader from '@material-ui/core/CardHeader';
import Typography from '@material-ui/core/Typography';
import { addDisplay } from 'modules/displays'
import FormControl from "@material-ui/core/FormControl";
import Select from "@material-ui/core/Select";
import MenuItem from "@material-ui/core/MenuItem";
import InputLabel from "@material-ui/core/InputLabel";
import Slider from "@material-ui/core/Slider";


const useStyles = makeStyles(theme => ({
    content: {
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'center',
        width: '100%',
        padding: theme.spacing(2),
        paddingBottom: 0,
    },
    formControl: {
        marginRight: theme.spacing(3),
    },
}));

const TransitionCard = ({ display }) => {
    const classes = useStyles();
    const dispatch = useDispatch();
    const schemas = useSelector(state => state.schemas.displays.schema.properties)
    const transition_mode = display.config[display.id] && display.config[display.id].config && display.config[display.id].config.transition_mode
    const transition_time = display.config[display.id] && display.config[display.id].config && display.config[display.id].config.transition_time

    const handleSetTransition = (displayId, config) => dispatch(addDisplay({
        "id": displayId, "config": config
    }));

    const onSliderChange = (e, newValue) => handleSetTransition(display.id, {
        transition_time: newValue
    })

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
        <Card variant="outlined" >
            <CardHeader title="Transitions" subheader="Seamlessly blend between effects" />
            <CardContent className={classes.content}>
                <FormControl className={classes.formControl}>
                    <Typography variant="subtitle2">
                        Transition Duration
                    </Typography>
                    <Slider
                        defaultValue={transition_time || schemas.transition_time.default}
                        onChangeCommitted={onSliderChange}
                        aria-labelledby="discrete-slider"
                        step={0.1}
                        min={schemas.transition_time.minimum}
                        max={schemas.transition_time.maximum}
                        marks={marks}
                        valueLabelDisplay="auto"
                    />
                </FormControl>
                <FormControl className={classes.formControl}>
                    <InputLabel id="demo-simple-select-helper-label">Select a transition effect</InputLabel>
                    <Select defaultValue={transition_mode || schemas.transition_mode.default} onChange={(e) => {
                        handleSetTransition(display.id, { transition_mode: e.target.value })
                    }} >
                        {schemas.transition_mode.enum.map((mode, i) => <MenuItem key={i} value={mode}>{mode}</MenuItem>)}
                    </Select>
                </FormControl>
            </CardContent>
        </Card>
    );
};

export default TransitionCard;
