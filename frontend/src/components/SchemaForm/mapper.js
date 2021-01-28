import React from 'react';
// import  {NumberField as DefaultNumberField} from 'react-schema-form/core';

import Slider from './customFields/Slider';

const mapper = {
    number: props => {
        const {
            form: {
                schema
            },
        } = props;

        if (schema.minimum !== undefined && schema.maximum !== undefined) {
            return <Slider {...props} />;
        }

        return <div {...props}/>
    },
};

export default mapper;
