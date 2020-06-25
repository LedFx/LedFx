import React, { useReducer } from 'react';
import PropTypes from 'prop-types';

import { makeStyles } from '@material-ui/core/styles';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import Grid from '@material-ui/core/Grid';
import TextField from '@material-ui/core/TextField';
import Button from '@material-ui/core/Button';
import Typography from '@material-ui/core/Typography';

const useStyles = makeStyles({
    button: {
        display: 'flex',
        justifyContent: 'flex-end',
        alignItems: 'center',
    },
});

const INITIAL_STATE = {
    name: '',
    error: '',
};

const AddSceneCard = ({ scenes = {}, addScene }) => {
    const classes = useStyles();
    const [state, dispatch] = useReducer(
        (state, payload) => ({
            ...state,
            ...payload,
        }),
        INITIAL_STATE
    );
    const { name, error } = state;

    const handleSave = () => {
        addScene(name);
    };

    const handleNameChanged = ({ target: { value } }) => {
        const error = validateInput(value, scenes.list) ? '' : 'Scene name already in use!';
        dispatch({ name: value, error });
    };

    return (
        <Card>
            <CardContent>
                <Typography variant="h5">Add Scene</Typography>
                <Typography>Save current effects of all devices as a Scene</Typography>
                <Grid container>
                    <Grid item xs={11}>
                        <TextField
                            error={!!error}
                            id="SceneNameInput"
                            label="Scene Name"
                            onChange={handleNameChanged}
                            fullWidth
                            helperText={error}
                        />
                    </Grid>
                    <Grid item xs={3} md={1} className={classes.button}>
                        <Button
                            color="primary"
                            size="medium"
                            aria-label="Save"
                            disabled={!!error || !name.length}
                            variant="contained"
                            onClick={handleSave}
                        >
                            Save
                        </Button>
                    </Grid>
                </Grid>
            </CardContent>
        </Card>
    );
};

const validateInput = (input, scenes) =>
    !scenes.some(p => p.name.toLowerCase() === input.toLowerCase());

AddSceneCard.propTypes = {
    addScene: PropTypes.func.isRequired,
    scenes: PropTypes.shape({
        isLoading: PropTypes.bool.isRequired,
        list: PropTypes.array.isRequired,
        dictionary: PropTypes.object.isRequired,
    }).isRequired,
};

export default AddSceneCard;
