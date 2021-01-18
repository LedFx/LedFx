import React from 'react';
import DefaultNumberField from 'react-schema-form/lib/Number';

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

        return <DefaultNumberField {...props}/>
    },
};

export default mapper;
