import React from 'react';
import PropTypes from 'prop-types';
import { makeStyles } from '@material-ui/core/styles';
import Select from '@material-ui/core/Select';
import InputLabel from '@material-ui/core/InputLabel';
import MenuItem from '@material-ui/core/MenuItem';
import FormControl from '@material-ui/core/FormControl';
import Typography from '@material-ui/core/Typography';

const useStyles = makeStyles(theme => ({
    control: {
        margin: theme.spacing(1),
        width: '100%',
    },
}));

function DropDown({ onChange, value, options, label }) {
    const classes = useStyles();

    const handleChange = ({ target: { value } }) => {
        if (onChange) {
            onChange(value);
        }
    };
    return (
        <FormControl className={classes.control}>
            {label && <InputLabel>{label}</InputLabel>}
            <Select value={value} onChange={handleChange}>
                <MenuItem value="" select="selected">
                    <Typography>None</Typography>
                </MenuItem>

                {options.map(({ display, value }) => {
                    return (
                        <MenuItem key={value} value={value}>
                            <Typography>{display}</Typography>
                        </MenuItem>
                    );
                })}
            </Select>
        </FormControl>
    );
}

DropDown.propTypes = {
    onChange: PropTypes.func.isRequired,
    options: PropTypes.array,
    value: PropTypes.string,
};
DropDown.defaultProps = {
    classes: '',
    options: [],
    value: '',
};

export default DropDown;
