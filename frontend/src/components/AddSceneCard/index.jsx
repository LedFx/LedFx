import React, { useReducer } from 'react';
import PropTypes from 'prop-types';

import { makeStyles } from '@material-ui/core/styles';
import Card from '@material-ui/core/Card';
import CardHeader from '@material-ui/core/CardHeader';
import CardContent from '@material-ui/core/CardContent';
import Box from '@material-ui/core/Box';
import TextField from '@material-ui/core/TextField';
import Button from '@material-ui/core/Button';
import SaveIcon from '@material-ui/icons/Save';

const useStyles = makeStyles(theme => ({
    button: {
        display: 'flex',
        justifyContent: 'flex-end',
        alignItems: 'center',
        margin: theme.spacing(1),
    },
}));

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
            <CardHeader title="Add Scene" subheader="Save current effects of all devices as a Scene" />
            <CardContent>
                <Box display="flex">
                    <Box item="true" flexGrow={1}>
                        <TextField
                            error={!!error}
                            id="SceneNameInput"
                            label="Scene Name"
                            onChange={handleNameChanged}
                            fullWidth
                            helperText={error}
                        />
                    </Box>
                    <Box item="true">
                        <Button
                            className={classes.button}
                            color="primary"
                            size="medium"
                            aria-label="Save"
                            disabled={!!error || !name.length}
                            variant="contained"
                            onClick={handleSave}
                            endIcon={<SaveIcon />}
                        >
                            Save Scene
                        </Button>
                    </Box>
                </Box>
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
