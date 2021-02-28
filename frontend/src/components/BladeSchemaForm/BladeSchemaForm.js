import React from 'react';
import PropTypes from 'prop-types';
import BladeColorDropDown from './BladeColorDropDown';
import BladeBoolean from './BladeBoolean';
import BladeSelect from './BladeSelect';
import BladeSlider from './BladeSlider';

const BladeSchemaForm = props => {
    const {
        schema,
        model,
        colorMode = 'picker',
        colorKeys = [],
        boolMode = 'switch',
        boolVariant = 'outlined',
        selectVariant = 'outlined',
        sliderVariant = 'outlined',
    } = props;
    const pickerKeys = [
        'color',
        'background_color',
        'color_lows',
        'color_mids',
        'color_high',
        'strobe_color',
        'lows_colour',
        'mids_colour',
        'high_colour',
        ...colorKeys,
    ];

    return (
        <div style={{ display: 'flex', flexWrap: 'wrap' }}>
            {pickerKeys.map(
                k =>
                    Object.keys(model).indexOf(k) !== -1 && (
                        <BladeColorDropDown
                            key={k}
                            type={colorMode === 'select' ? 'text' : 'color'}
                            clr={k}
                        />
                    )
            )}

            {Object.keys(schema.properties).map((s, i) => {
                switch (schema.properties[s].type) {
                    case 'boolean':
                        return (
                            <BladeBoolean
                                type={boolMode}
                                variant={boolVariant}
                                key={i}
                                model={model}
                                schema={schema.properties[s]}
                            />
                        );
                    case 'string':
                        return (
                            schema.properties[s].enum &&
                            pickerKeys.indexOf(s) === -1 && (
                                <BladeSelect
                                    variant={selectVariant}
                                    model={model}
                                    schema={schema.properties[s]}
                                    model_id={s}
                                    key={i}
                                />
                            )
                        );

                    case 'number':
                        return (
                            <BladeSlider
                                variant={sliderVariant}
                                key={i}
                                model_id={s}
                                model={model}
                                schema={schema.properties[s]}
                            />
                        );

                    case 'integer':
                        return (
                            <BladeSlider
                                variant={sliderVariant}
                                step={1}
                                key={i}
                                model_id={s}
                                model={model}
                                schema={schema.properties[s]}
                            />
                        );

                    default:
                        return <>Unsupported type: {schema.properties[s].type}</>;
                }
            })}
        </div>
    );
};

BladeSchemaForm.propTypes = {
    colorMode: PropTypes.oneOf(['picker', 'select']),
    boolMode: PropTypes.oneOf(['switch', 'checkbox', 'button']),
    boolVariant: PropTypes.oneOf(['outlined', 'contained', 'text']),
    selectVariant: PropTypes.string, // outlined | any
    sliderVariant: PropTypes.string, // outlined | any
    colorKeys: PropTypes.array,
    schema: PropTypes.object.isRequired,
    model: PropTypes.object.isRequired,
};

export default BladeSchemaForm;
