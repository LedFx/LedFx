import React from 'react';
import PropTypes from 'prop-types';
import { makeStyles } from '@material-ui/core/styles';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import CardActions from '@material-ui/core/CardActions';
import Button from '@material-ui/core/Button';
import red from '@material-ui/core/colors/red';

import SceneConfigTable from 'components/SceneCard/SceneConfigTable';

const useStyles = makeStyles(theme => ({
    deleteButton: {
        color: theme.palette.getContrastText(red[500]),
        backgroundColor: red[500],
        '&:hover': {
            backgroundColor: red[700],
        },
        margin: theme.spacing(1),
        float: 'right',
    },
    button: {
        margin: theme.spacing(1),
        float: 'right',
    },
    submitControls: {
        flex: 1,
        justifyContent: 'flex-end',
    },
}));

export default function SceneCard({ scene, activateScene, deleteScene }) {
    const classes = useStyles();

    const handleActivate = () => {
        activateScene(scene.id);
    };

    const handleDelete = () => {
        deleteScene(scene.id);
    };

    return (
        <Card>
            <CardContent>
                <h3>{scene.name}</h3>
                {scene.devices && <SceneConfigTable devices={scene.devices} />}
            </CardContent>
            <CardActions className={classes.submitControls}>
                <Button
                    className={classes.button}
                    color="primary"
                    size="medium"
                    aria-label="Activate"
                    variant="contained"
                    onClick={handleActivate}
                >
                    Activate
                </Button>
                <Button
                    className={classes.deleteButton}
                    color="secondary"
                    size="medium"
                    aria-label="Delete"
                    variant="contained"
                    onClick={handleDelete}
                >
                    Delete
                </Button>
            </CardActions>
        </Card>
    );
}

SceneCard.propTypes = {
    scene: PropTypes.object.isRequired,
    deleteScene: PropTypes.func.isRequired,
    activateScene: PropTypes.func.isRequired,
};
