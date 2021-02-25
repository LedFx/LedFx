import React from 'react';
import TextField from '@material-ui/core/TextField';

export const getWled = async ip => {
    const res = await fetch(`http://${ip}/json/info`);
    const wled = await res.json();

    if (wled.ver && wled.name && wled.leds && wled.leds.count && wled.arch) {
        alert(
            `WLED-${wled.ver} Device '${wled.name}' detected, running ${wled.leds.count} Pixels on a ${wled.arch}`
        );
    }
    return wled;
};

const mapper = {
    text: props => {
        const {
            form: { schema },
        } = props;

        console.log('YZ08:', schema);

        if (schema.title === 'Ip Address') {
            return (
                <TextField
                    {...props}
                    label={schema.title}
                    helperText={schema.description}
                    onChange={e => {
                        if (e.target.value.length > 7) {
                            getWled(e.target.value);
                        }
                    }}
                />
            );
        }

        return <div {...props} />;
    },
};

export default mapper;
