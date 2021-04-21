import React, { useState, useEffect } from 'react';
import { useSelector } from 'react-redux';
import PropTypes from 'prop-types';
import { SchemaForm, utils } from 'react-schema-form';
import { makeStyles } from '@material-ui/core/styles';
import Typography from '@material-ui/core/Typography';
import Button from '@material-ui/core/Button';
import DialogActions from '@material-ui/core/DialogActions';
import Box from '@material-ui/core/Box';

import CancelIcon from '@material-ui/icons/Cancel';
import CheckCircleIcon from '@material-ui/icons/CheckCircle';
import CasinoIcon from '@material-ui/icons/Casino';

import DropDown from 'components/forms/DropDown';
import mapper from 'components/SchemaForm/mapper';
import BladeDropDown from '../BladeSchemaForm/BladeEffectDropDown';

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
        '& > *': {
            marginLeft: theme.spacing(2),
        },
    },
    expandIcon: {
        transform: 'rotate(180deg)',
    },
}));

const EffectControl = ({ effect, ...props }) => {
    const [selectedType, setSelectedType] = useState('')
    const [model, setModel] = useState({})
    const schemas = useSelector(state => state.schemas)
    const classes = useStyles();
    // useEffect(() => {
    //     if (effect.type) {
    //         handleTypeChange(effect.type, effect.config);
    //     }
    // }, [effect.type, effect.config, handleTypeChange])



    const handleTypeChange = (value = '', initial = {}) => {
        const { onTypeChange } = props;
        setSelectedType(value);
        setModel(initial);
        if (onTypeChange) {
            onTypeChange(value);
        }
    };

    const onModelChange = (key, val) => {
        const modelc = utils.selectOrSet(key, model, val);
        setModel({ modelc });
    };

    const handleSubmit = e => {
        const { onSubmit, device } = props;
        e.preventDefault();
        if (onSubmit) {
            onSubmit({ deviceId: device.id, type: selectedType, config: model });
        }
    };

    const handleRandomize = e => {
        const { onSubmit, device } = props;
        e.preventDefault();
        if (onSubmit) {
            onSubmit({ deviceId: device.id, type: selectedType, config: 'RANDOMIZE' });
        }
    };

    const handleClearEffect = ({ onClear, device }) => {
        onClear(device.id);
    };




    const currentSchema = {
        type: 'object',
        title: 'Configuration',
        properties: {},
        ...(selectedType ? schemas.effects[selectedType].schema : {}),
    };

    const requiredKeys = Object.keys(currentSchema.properties);

    if (schemas.effects) {
        return (
            <>
                <Typography variant="h5">Effect Control</Typography>
                <Typography variant="body1" color="textSecondary">
                    Set and configure effects!
                    </Typography>
                <form onSubmit={handleSubmit} className={classes.form}>
                    <BladeDropDown effects={Object.keys(schemas?.effects)} />
                    <DropDown
                        label="Type"
                        value={selectedType}
                        options={Object.keys(schemas?.effects).map(key => ({
                            value: key,
                            display: key,
                        }))}
                        onChange={handleTypeChange}
                    />

                    <SchemaForm
                        className={classes.schemaForm}
                        schema={currentSchema}
                        form={requiredKeys}
                        model={model}
                        onModelChange={onModelChange}
                        mapper={mapper}
                    />

                    <DialogActions className={classes.bottomContainer}>
                        {selectedType && (
                            <Button
                                onClick={handleRandomize}
                                endIcon={<CasinoIcon />}
                                color="primary"
                            >
                                Randomize
                            </Button>
                        )}
                        <Box
                            flex={1}
                            display="flex"
                            justifyContent="flex-end"
                            className={classes.actionButtons}
                        >
                            <Button
                                className={classes.button}
                                onClick={handleClearEffect}
                                color="primary"
                                endIcon={<CancelIcon />}
                            >
                                Clear Effect
                                </Button>
                            <Button
                                className={classes.button}
                                type="submit"
                                variant="contained"
                                color="primary"
                                disabled={!selectedType}
                                endIcon={<CheckCircleIcon />}
                            >
                                Set Effect
                                </Button>
                        </Box>
                    </DialogActions>
                </form>
            </>
        );
    }

    return <p>Loading</p>;

}

EffectControl.propTypes = {
    classes: PropTypes.object.isRequired,
    schemas: PropTypes.object.isRequired,
    device: PropTypes.object.isRequired,
    effect: PropTypes.object.isRequired,
};

export default EffectControl;
