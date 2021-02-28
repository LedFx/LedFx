import React from 'react';
import PropTypes from 'prop-types';
import { makeStyles } from '@material-ui/core/styles';
import { Select, MenuItem } from '@material-ui/core/';
const useStyles = makeStyles(theme => ({
    wrapper: {
        minWidth: '200px',
        padding: '10px 1.2rem 2px 1.2rem',
        border: `1px solid #999`,
        borderRadius: '10px',
        position: 'relative',
        margin: '0.5rem',
        display: 'flex',
        alignItems: 'center',
        '& > label': {
            top: '-0.7rem',
            display: 'flex',
            alignItems: 'center',
            left: '1rem',
            padding: '0 0.3rem',
            position: 'absolute',
            fontVariant: 'all-small-caps',
            backgroundColor: theme.palette.background.paper,
            boxSizing: 'border-box',
        },
    },
}));
const BladeSelect = ({ variant = 'outlined', schema, model, model_id }) => {
    // console.log(model, schema, model_id);
    const classes = useStyles();

    const Frame = ({ children }) =>
        variant === 'outlined' ? (
            <div className={classes.wrapper}>
                <label>{schema.title}</label>
                {children}
            </div>
        ) : (
            children
        );

    return (
        <Frame>
            <Select
                style={{ flexGrow: variant === 'outlined' ? 1 : 'unset' }}
                disableUnderline
                defaultValue={schema.default}
                value={model && model[model_id]}
                onChange={(e, b) => console.log(e, b)}
            >
                {schema.enum.map((item, i) => (
                    <MenuItem key={i} value={item}>
                        {item}
                    </MenuItem>
                ))}
            </Select>
        </Frame>
    );
};

BladeSelect.propTypes = {
    variant: PropTypes.string,
    schema: PropTypes.object.isRequired,
    model: PropTypes.object.isRequired,
    model_id: PropTypes.string.isRequired,
};

export default BladeSelect;
