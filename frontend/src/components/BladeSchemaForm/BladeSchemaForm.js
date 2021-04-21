import React from 'react';
import { useDispatch } from 'react-redux';
import PropTypes from 'prop-types';
import BladeColorDropDown from './BladeColorDropDown';
import BladeBoolean from './BladeBoolean';
import BladeSelect from './BladeSelect';
import BladeSlider from './BladeSlider';
import { setDisplayEffect } from 'modules/selectedDisplay';
import {
    Fab,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogContentText,
    Select,
    DialogActions,
    Button,
    InputLabel,
    MenuItem,
    FormControl,
} from '@material-ui/core';
import SettingsIcon from '@material-ui/icons/Settings';
const BladeSchemaForm = props => {
    const dispatch = useDispatch();
    const {
        schema,
        model,
        display_id,
        selectedType,
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
    const [open, setOpen] = React.useState(false);
    const [_boolMode, _setBoolMode] = React.useState(boolMode);
    const [_boolVariant, _setBoolVariant] = React.useState(boolVariant);
    const [_selectVariant, _setSelectVariant] = React.useState(selectVariant);
    const [_sliderVariant, _setSliderVariant] = React.useState(sliderVariant);
    const [_colorMode, _setColorMode] = React.useState(colorMode);

    const handleClickOpen = () => {
        setOpen(true);
    };

    const handleClose = () => {
        setOpen(false);
    };
    const handleEffectConfig = (display_id, config) =>
        dispatch(
            setDisplayEffect(display_id, {
                displayId: display_id,
                type: selectedType,
                config: config,
            })
        );

    return (
        <div style={{ display: 'flex', flexWrap: 'wrap' }}>
            {parseInt(window.localStorage.getItem('BladeMod')) > 2 && (
                <Fab
                    onClick={handleClickOpen}
                    variant="round"
                    color="primary"
                    size="small"
                    style={{ position: 'absolute', right: '1rem', top: '1rem' }}
                >
                    <SettingsIcon />
                </Fab>
            )}
            {pickerKeys.map(
                k =>
                    Object.keys(model).indexOf(k) !== -1 && (
                        <BladeColorDropDown
                            selectedType={selectedType}
                            model={model}
                            key={k}
                            type={_colorMode === 'select' ? 'text' : 'color'}
                            clr={k}
                        />
                    )
            )}

            {Object.keys(schema.properties).map((s, i) => {
                switch (schema.properties[s].type) {
                    case 'boolean':
                        return (
                            <BladeBoolean
                                type={_boolMode}
                                variant={_boolVariant}
                                key={i}
                                model={model}
                                model_id={s}
                                schema={schema.properties[s]}
                                onClick={(model_id, value) => {
                                    const c = {};
                                    c[model_id] = value;
                                    return handleEffectConfig(display_id, c);
                                }}
                            />
                        );
                    case 'string':
                        return (
                            schema.properties[s].enum &&
                            pickerKeys.indexOf(s) === -1 && (
                                <BladeSelect
                                    model={model}
                                    variant={_selectVariant}
                                    schema={schema.properties[s]}
                                    model_id={s}
                                    key={i}
                                    onChange={(model_id, value) => {
                                        const c = {};
                                        c[model_id] = value;
                                        return handleEffectConfig(display_id, c);
                                    }}
                                />
                            )
                        );

                    case 'number':
                        return (
                            <BladeSlider
                                variant={_sliderVariant}
                                key={i}
                                model_id={s}
                                model={model}
                                schema={schema.properties[s]}
                                onChange={(model_id, value) => {
                                    const c = {};
                                    c[model_id] = value;
                                    return handleEffectConfig(display_id, c);
                                }}
                            />
                        );

                    case 'integer':
                        return (
                            <BladeSlider
                                variant={_sliderVariant}
                                step={1}
                                key={i}
                                model_id={s}
                                model={model}
                                schema={schema.properties[s]}
                                onChange={(model_id, value) => {
                                    const c = {};
                                    c[model_id] = value;
                                    return handleEffectConfig(display_id, c);
                                }}
                            />
                        );

                    default:
                        return <>Unsupported type: {schema.properties[s].type}</>;
                }
            })}
            <Dialog open={open} onClose={handleClose} aria-labelledby="form-dialog-title">
                <DialogTitle id="form-dialog-title">Blade's SchemaForm Settings</DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        Customize the appearance of dynamically generated forms
                    </DialogContentText>
                    <FormControl>
                        <InputLabel id="ColorVariantLabel">Color Mode</InputLabel>
                        <Select
                            labelId="ColorVariantLabel"
                            id="ColorVariant"
                            value={_colorMode}
                            onChange={e => _setColorMode(e.target.value)}
                        >
                            <MenuItem value={'picker'}>Picker</MenuItem>
                            <MenuItem value={'select'}>Select</MenuItem>
                        </Select>
                    </FormControl>
                    <FormControl>
                        <InputLabel id="BoolModeLabel">Bool Mode</InputLabel>
                        <Select
                            labelId="BoolModeLabel"
                            id="BoolMode"
                            value={_boolMode}
                            onChange={e => _setBoolMode(e.target.value)}
                        >
                            <MenuItem value={'switch'}>Switch</MenuItem>
                            <MenuItem value={'checkbox'}>Checkbox</MenuItem>
                            <MenuItem value={'button'}>Button</MenuItem>
                        </Select>
                    </FormControl>
                    <FormControl>
                        <InputLabel id="BoolVariantLabel">Bool Variant</InputLabel>
                        <Select
                            labelId="BoolVariantLabel"
                            id="BoolVariant"
                            value={_boolVariant}
                            onChange={e => _setBoolVariant(e.target.value)}
                        >
                            <MenuItem value={'text'}>Text</MenuItem>
                            <MenuItem value={'outlined'}>Outlined</MenuItem>
                        </Select>
                    </FormControl>
                    <FormControl>
                        <InputLabel id="SelectVariantLabel">Select Variant</InputLabel>
                        <Select
                            labelId="SelectVariantLabel"
                            id="SelectVariant"
                            value={_selectVariant}
                            onChange={e => _setSelectVariant(e.target.value)}
                        >
                            <MenuItem value={'text'}>Text</MenuItem>
                            <MenuItem value={'outlined'}>Outlined</MenuItem>
                            <MenuItem value={'contained'}>Contained</MenuItem>
                        </Select>
                    </FormControl>
                    <FormControl>
                        <InputLabel id="SliderVariantLabel">Slider Variant</InputLabel>
                        <Select
                            labelId="SliderVariantLabel"
                            id="SliderVariant"
                            value={_sliderVariant}
                            onChange={e => _setSliderVariant(e.target.value)}
                        >
                            <MenuItem value={'text'}>Text</MenuItem>
                            <MenuItem value={'outlined'}>Outlined</MenuItem>
                        </Select>
                    </FormControl>

                    <DialogActions>
                        <Button onClick={handleClose} variant="contained" color="primary">
                            Ok
                        </Button>
                    </DialogActions>
                </DialogContent>
            </Dialog>
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
    display_id: PropTypes.string.isRequired,
    selectedType: PropTypes.string.isRequired,
};

export default BladeSchemaForm;
