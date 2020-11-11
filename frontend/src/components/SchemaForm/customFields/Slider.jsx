import React from 'react';
import ComposedComponent from 'react-schema-form/lib/ComposedComponent';

import { makeStyles } from '@material-ui/core/styles';
import Slider from '@material-ui/core/Slider';
import InputLabel from '@material-ui/core/InputLabel';
import Box from '@material-ui/core/Box';
import debounce from 'debounce';

const useStyles = makeStyles(theme => ({
    root: {
        margin: theme.spacing(1),
        padding: theme.spacing(1),
        width: '100%',
        flex: '1 0 30%',
    },
    valueLabel: {
        transformOrigin: 'top right',
    }
}));

function valuetext(value) {
    return value.toString();
}

const SliderComponent = props => {
    const {
        form,
        form: { schema, type },
        value,
        onChangeValidate,
    } = props;

    const debouncedOnChangeHandler = debounce(onChangeValidate, 200)

    const onChange = (e, newValue) => {
        debouncedOnChangeHandler(newValue);
    };

    const classes = useStyles();

    const marks = [
        {
            value: schema.minimum,
            label: schema.minimum,
        },
        {
            value: schema.maximum,
            label: schema.maximum,
        },
    ];

    return (
        <div className={classes.root}>
            <Box display="flex" justifyContent="space-between">
                <InputLabel id="discrete-slider" shrink>
                    {schema.title}
                </InputLabel>
                <InputLabel shrink className={classes.valueLabel}>
                    {value}
                </InputLabel>
            </Box>
            <Slider
                defaultValue={schema.default}
                getAriaValueText={valuetext}
                aria-labelledby="discrete-slider"
                step={0.001}
                marks={marks}
                valueLabelDisplay="auto"
                min={schema.minimum}
                max={schema.maximum}
                onChange={onChange}
            />
        </div>
    );
};

// export default SliderComponent;
export default ComposedComponent(SliderComponent);
