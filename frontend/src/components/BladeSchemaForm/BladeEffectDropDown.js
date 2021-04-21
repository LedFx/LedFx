import React from 'react';
import { useSelector, useDispatch } from 'react-redux';
import ToggleButton from '@material-ui/lab/ToggleButton';
import ToggleButtonGroup from '@material-ui/lab/ToggleButtonGroup';
import InputLabel from '@material-ui/core/InputLabel';
import MenuItem from '@material-ui/core/MenuItem';
import ListSubheader from '@material-ui/core/ListSubheader';
import FormControl from '@material-ui/core/FormControl';
import Select from '@material-ui/core/Select';
import { setDisplayEffect } from 'modules/selectedDisplay';
import { makeStyles } from '@material-ui/core/styles';

const useStyles = makeStyles(theme => ({
    FormRow: {
        display: 'flex',
        flexDirection: 'row',
        border: '1px solid #999',
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
    FormListHeaders: {
        background: theme.palette.primary.main,
        color: '#fff',
    },
    FormListItem: {
        paddingLeft: '2rem',
    },
    FormToggleWrapper: {
        '@media (max-width: 580px)': {
            order: -1,
        },
    },

    FormToggle: {
        '@media (max-width: 580px)': {
            flexGrow: 1,
        },
    },
}));

const BladeDropDown = () => {
    const dispatch = useDispatch();
    const classes = useStyles();
    const effects = useSelector(state => state.schemas.effects);
    const effectNames = Object.keys(effects).map(eid => ({
        name: effects[eid].name,
        id: effects[eid].id,
        category: effects[eid].category,
    }));
    const selectedDisplay = useSelector(state => state.selectedDisplay);
    const { display } = selectedDisplay;

    let group = effectNames.reduce((r, a) => {
        r[a.category] = [...(r[a.category] || []), a];
        return r;
    }, {});

    const [formats, setFormats] = React.useState(() => Object.keys(group).map(c => c || []));

    const handleFormat = (event, newFormats) => {
        setFormats(newFormats);
    };
    const onEffectTypeChange = e =>
        dispatch(
            setDisplayEffect(display.id, {
                displayId: display.id,
                type: e.target.value,
            })
        );
    // dispatch(setDisplayEffect(display.id, { displayId: display.id, type: e.target.value }));

    return (
        <>
            <FormControl className={classes.FormRow}>
                <InputLabel htmlFor="grouped-select" className={classes.FormLabel}>
                    Effect Type
                </InputLabel>
                <Select
                    defaultValue={display.config[display.id].effect.type}
                    onChange={onEffectTypeChange}
                    id="grouped-select"
                    className={classes.FormSelect}
                >
                    <MenuItem value="">
                        <em>None</em>
                    </MenuItem>
                    {effects &&
                        Object.keys(group).map(
                            c =>
                                formats.indexOf(c) !== -1 && [
                                    <ListSubheader
                                        className={classes.FormListHeaders}
                                        color="primary"
                                    >
                                        {c}
                                    </ListSubheader>,
                                    group[c].map(e => (
                                        <MenuItem className={classes.FormListItem} value={e.id}>
                                            {e.name}
                                        </MenuItem>
                                    )),
                                ]
                        )}
                </Select>
                <ToggleButtonGroup
                    value={formats}
                    onChange={handleFormat}
                    aria-label="text formatting"
                    className={classes.FormToggleWrapper}
                >
                    {effects &&
                        Object.keys(group).map((c, i) => (
                            <ToggleButton
                                className={classes.FormToggle}
                                key={i}
                                value={c}
                                aria-label={c}
                            >
                                {c}
                            </ToggleButton>
                        ))}
                </ToggleButtonGroup>
            </FormControl>
        </>
    );
};

export default BladeDropDown;
