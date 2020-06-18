import React from 'react';
import PropTypes from 'prop-types';
import { SchemaForm } from 'react-schema-form';

import { makeStyles } from '@material-ui/core/styles';
import Collapse from '@material-ui/core/Collapse';

const useStyles = makeStyles(theme => ({
    flexWrap: {
        display: 'flex',
        flexWrap: 'wrap',
    },
    schemaForm: {
        display: 'flex',
        flexWrap: 'wrap',
    },
}));

function AdditionalProperties({ form, model, schema, onChange, open }) {
    const classes = useStyles();

    const handleChange = (...args) => {
        if (onChange) {
            onChange(...args);
        }
    };

    return (
        <Collapse in={open}>
            <div className={classes.flexWrap}>
                <SchemaForm
                    className={classes.schemaForm}
                    schema={schema}
                    form={form}
                    model={model}
                    onModelChange={handleChange}
                />
            </div>
        </Collapse>
    );
}

AdditionalProperties.propTypes = {
    onChange: PropTypes.func.isRequired,
    form: PropTypes.array,
    model: PropTypes.object,
    scheme: PropTypes.object,
};
AdditionalProperties.defaultProps = {
    classes: '',
    form: [],
    model: {},
    scheme: {},
};

export default AdditionalProperties;
