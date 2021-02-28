import React from 'react';
import PropTypes from 'prop-types';
import { makeStyles } from '@material-ui/core/styles';
import { Slider, Input } from '@material-ui/core/';
const useStyles = makeStyles(theme => ({
    input: {
        marginLeft: '1rem',
    },
    wrapper: {
        minWidth: '250px',
        padding: '10px 1.2rem 2px 1.2rem',
        border: `1px solid #999`,
        borderRadius: '10px',
        position: 'relative',
        margin: '0.5rem',
        display: 'flex',
        '& > label': {
            top: '-0.7rem',
            display: 'flex',
            alignItems: 'center',
            left: '1rem',
            padding: '0 0.3rem',
            position: 'absolute',
            fontVariant: 'all-small-caps',
            backgroundColor: theme.palette.background.paper,
            boxSizing: 'border-box',
        },
    },
}));
const BladeSlider = ({ variant = 'outlined', schema, model, model_id, step }) => {
    const classes = useStyles();
    return variant === 'outlined' ? (
        <div className={classes.wrapper}>
            <label>{schema.title}</label>
            <BladeSliderInner schema={schema} model={model} model_id={model_id} step={step} />
        </div>
    ) : (
        <BladeSliderInner schema={schema} model={model} model_id={model_id} />
    );
};

const BladeSliderInner = ({ schema, model, model_id, step }) => {
    // console.log(model, schema, model_id);
    const classes = useStyles();
    const [value, setValue] = React.useState(model[model_id] || schema.default);

    const handleSliderChange = (event, newValue) => {
        if (newValue !== value) {
            setValue(newValue);
        }
    };

    const handleInputChange = event => {
        setValue(event.target.value === '' ? '' : Number(event.target.value));
    };
    const handleBlur = () => {
        if (value < schema.minimum) {
            setValue(schema.minimum);
        } else if (value > schema.maximum) {
            setValue(schema.maximum);
        }
    };

    return (
        <>
            <Slider
                aria-labelledby="input-slider"
                valueLabelDisplay="auto"
                marks
                step={step || (schema.maximum > 1 ? 0.1 : 0.01)}
                min={schema.minimum}
                max={schema.maximum}
                value={typeof value === 'number' ? value : 0}
                onChange={handleSliderChange}
                // defaultValue={model[model_id] || schema.default}
                // value={model && model[model_id]}
            />
            <Input
                disableUnderline
                className={classes.input}
                value={value}
                margin="dense"
                onChange={handleInputChange}
                onBlur={handleBlur}
                inputProps={{
                    step: schema.maximum > 1 ? 0.1 : 0.01,
                    min: schema.minimum,
                    max: schema.maximum,
                    type: 'number',
                    'aria-labelledby': 'input-slider',
                }}
            />
        </>
    );
};

BladeSlider.propTypes = {
    variant: PropTypes.string,
    schema: PropTypes.object.isRequired,
    model: PropTypes.object.isRequired,
    model_id: PropTypes.string.isRequired,
};

export default BladeSlider;
