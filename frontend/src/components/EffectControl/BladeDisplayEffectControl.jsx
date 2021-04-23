import React, { useState, useEffect } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import PropTypes from 'prop-types';
import { makeStyles } from '@material-ui/core/styles';
import Typography from '@material-ui/core/Typography';
import Button from '@material-ui/core/Button';
import DialogActions from '@material-ui/core/DialogActions';
import Box from '@material-ui/core/Box';
import { getEffectPresets } from 'modules/presets';
import BladeDropDown from '../BladeSchemaForm/BladeEffectDropDown';
import BladeSchemaForm from '../BladeSchemaForm/BladeSchemaForm';
import { Delete, Casino } from '@material-ui/icons';

const useStyles = makeStyles(theme => ({
    form: {
        display: 'flex',
        flexWrap: 'wrap',
    },
    schemaForm: {
        display: 'flex',
        flexWrap: 'wrap',
        width: '100%',
    },
    bottomContainer: {
        flex: 1,
        marginTop: 8,
    },
    actionButtons: {
        fontSize: '2rem',
        '& >button': {
            marginRight: '1rem',
        },
        '& >button:last-child': {
            marginRight: '0rem'
        }
    },
    expandIcon: {
        transform: 'rotate(180deg)',
    },
}));

const DisplayEffectControl = ({ onSubmit, onClear, display, effect }) => {
    const [selectedType, setSelectedType] = useState('')
    const [model, setModel] = useState({})
    const schemas = useSelector(state => state.schemas)
    const classes = useStyles();
    const dispatch = useDispatch();


    useEffect(() => {
        const handleTypeChange = (value = '', initial = {}) => {
            setSelectedType(value);
            setModel(initial);
            dispatch(getEffectPresets(value))

        };
        if (effect.type) {
            handleTypeChange(effect.type, effect.config)
        }
    }, [effect, dispatch])



    const handleSubmit = e => {

        e.preventDefault();
        if (onSubmit) {
            onSubmit({ displayId: display.id, type: selectedType, config: model });
        }
    };

    const handleRandomize = e => {

        e.preventDefault();
        if (onSubmit) {
            onSubmit({ displayId: display.id, type: selectedType, config: 'RANDOMIZE' });
        }
    };

    const handleClearEffect = () => {
        onClear(display.id);
    };


    const currentSchema = {
        type: 'object',
        title: 'Configuration',
        properties: {},
        ...(selectedType ? schemas.effects[selectedType].schema : {}),
    };

    // console.log(currentSchema, model)
    if (schemas.effects) {
        return (
            <>
                <Typography variant="h5">Effect Control</Typography>
                <Typography variant="body1" color="textSecondary">
                    Set and configure effects
                </Typography>
                <BladeDropDown />
                {effect && effect.config && <BladeSchemaForm schema={currentSchema} model={model} display_id={display.id} selectedType={selectedType} />}
                {/* <div style={{ display: 'flex', flexWrap: 'wrap' }}>
                    {pickerKeys.map(k => Object.keys(model).indexOf(k) !== -1 && <BladeColorDropDown key={k} type={"color"} clr={k} />)}

                    {Object.keys(currentSchema.properties).map((s, i) => currentSchema.properties[s].type === 'boolean' && < BladeBoolean key={i} model={model} schema={currentSchema.properties[s]} />)}
                    {Object.keys(currentSchema.properties).map((s, i) =>
                        currentSchema.properties[s].type === 'string' &&
                        currentSchema.properties[s].enum &&
                        pickerKeys.indexOf(s) === -1 &&
                        <BladeSelect model={model} schema={currentSchema.properties[s]} model_id={s} key={`${s}${i}`} />)
                    }
                    {Object.keys(currentSchema.properties).map((s, i) => currentSchema.properties[s].type === 'number' && < BladeSlider key={i} model_id={s} model={model} schema={currentSchema.properties[s]} />)}

                </div> */}
                <form onSubmit={handleSubmit} className={classes.form}>

                    <DialogActions className={classes.bottomContainer}>
                        <Box
                            flex={1}
                            display="flex"
                            justifyContent="flex-end"
                            className={classes.actionButtons}
                        >
                            {selectedType && (
                                <Button
                                    onClick={handleRandomize}
                                    variant="outlined"
                                ><Casino />
                                </Button>
                            )}
                            <Button
                                className={classes.button}
                                variant="outlined"
                                onClick={handleClearEffect}
                            ><Delete />
                            </Button>

                        </Box>
                    </DialogActions>
                </form>
            </>
        );
    }

    return <p>Loading</p>;

}

DisplayEffectControl.propTypes = {
    display: PropTypes.object.isRequired,
    effect: PropTypes.object.isRequired,
};

export default DisplayEffectControl

