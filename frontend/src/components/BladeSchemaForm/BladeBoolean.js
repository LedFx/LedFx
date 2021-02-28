import React from 'react';
import { makeStyles } from '@material-ui/core/styles';
import { FormControlLabel, Switch, Checkbox, Button } from '@material-ui/core/';
const useStyles = makeStyles(theme => ({
    paper: {
        border: '1px solid',
        display: 'flex',
        flexWrap: 'wrap',
        maxWidth: '320px',
        padding: theme.spacing(1),
        backgroundColor: theme.palette.background.paper,
    },
    wrapper: {
        minWidth: '140px',
        padding: '10px 10px 2px 10px',
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
const BladeBoolean = ({ type = 'switch', variant = 'outlined', schema, model, model_id }) => {
    // console.log(model);
    const classes = useStyles();
    const Frame = ({ children }) =>
        variant === 'outlined' ? (
            <div className={classes.wrapper}>
                <label>{schema.title}</label>
                {children}
            </div>
        ) : variant === 'text' ? (
            <FormControlLabel control={children} label={schema.title} />
        ) : (
            { children }
        );
    // console.log(schema.title, schema.description, schema.default);
    switch (type) {
        case 'switch':
            return (
                <Frame>
                    <Switch
                        defaultValue={schema.default}
                        checked={model && model[model_id]}
                        onChange={(e, b) => console.log(e, b)}
                        name={schema.title}
                        color="primary"
                    />
                </Frame>
            );
        case 'checkbox':
            return (
                <Frame>
                    <Checkbox
                        defaultValue={schema.default}
                        checked={model && model[model_id]}
                        onChange={(e, b) => console.log(e, b)}
                        name="checkedB"
                        color="primary"
                    />
                </Frame>
            );
        case 'button':
            return (
                <Button color={'primary'} variant={variant}>
                    {schema.title}
                </Button>
            );

        default:
            return <div>unset</div>;
    }
};

export default BladeBoolean;
