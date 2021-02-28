import React, { useState } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import InputLabel from '@material-ui/core/InputLabel';
import MenuItem from '@material-ui/core/MenuItem';
import FormControl from '@material-ui/core/FormControl';
import Select from '@material-ui/core/Select';
import { setDisplayEffect } from 'modules/selectedDisplay';
import { makeStyles } from '@material-ui/core/styles';
import BladeColorPicker from './BladeColorPicker';

const useStyles = makeStyles(theme => ({
    FormRow: {
        display: 'flex',
        flexDirection: 'row',
        border: '1px solid',
        borderRadius: '10px',
        '@media (max-width: 580px)': {
            flexDirection: 'column',
        },
    },
    FormLabel: {
        marginLeft: '1rem',
        paddingTop: '0.5rem',
        '@media (max-width: 580px)': {
            display: 'none',
        },
    },
    FormSelect: {
        flexGrow: 1,
        marginLeft: '1rem',
        paddingTop: '0.5rem',
        '&:before, &:after': {
            display: 'none',
        },
        '& > .MuiSelect-select:focus': {
            backgroundColor: 'unset',
        },
    },
}));

const BladeColorDropDown = ({ clr = 'color', type = 'both' }) => {
    // console.log(type);
    const dispatch = useDispatch();
    const classes = useStyles();
    const effects = useSelector(state => state.schemas.effects);
    const selectedDisplay = useSelector(state => state.selectedDisplay);
    const { display, effect } = selectedDisplay;
    const curEffSchema = effects[display.config[display.id].effect.type];
    const colors =
        curEffSchema &&
        curEffSchema.schema.properties[clr] &&
        curEffSchema.schema.properties[clr].enum;
    const [col, setCol] = useState(effect.config && effect.config[clr]);
    const sendColor = e => {
        setCol(e);
        return (
            display &&
            dispatch(
                setDisplayEffect(display.id, {
                    displayId: display.id,
                    type: display.config[display.id].effect.type,
                    config: { [clr]: e },
                })
            )
        );
    };
    const onEffectTypeChange = e => {
        setCol(e.target.value);
        return (
            display &&
            dispatch(
                setDisplayEffect(display.id, {
                    displayId: display.id,
                    type: display.config[display.id].effect.type,
                    config: { [clr]: e.target.value },
                })
            )
        );
    };

    return (
        <div style={{ display: 'flex', alignItems: 'center' }}>
            {(type === 'text' || type === 'both') && (
                <FormControl className={classes.FormRow}>
                    <InputLabel htmlFor="grouped-select" className={classes.FormLabel}>
                        {clr.replaceAll('_', ' ')}
                    </InputLabel>
                    <Select
                        value={col}
                        onChange={onEffectTypeChange}
                        id="grouped-select"
                        className={classes.FormSelect}
                    >
                        {colors &&
                            colors.map(c => (
                                <MenuItem className={classes.FormListItem} key={c} value={c}>
                                    {c}
                                </MenuItem>
                            ))}
                    </Select>
                </FormControl>
            )}

            {(type === 'color' || type === 'both') && (
                <BladeColorPicker col={col} clr={clr} sendColor={sendColor} />
            )}
        </div>
    );
};

export default BladeColorDropDown;
