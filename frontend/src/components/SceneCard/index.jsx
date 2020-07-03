import React from 'react';
import PropTypes from 'prop-types';
import { makeStyles } from '@material-ui/core/styles';
import Card from '@material-ui/core/Card';
import CardHeader from '@material-ui/core/CardHeader';
import CardContent from '@material-ui/core/CardContent';
import CardActions from '@material-ui/core/CardActions';
import Button from '@material-ui/core/Button';
import DeleteIcon from '@material-ui/icons/Delete';
import CheckCircleIcon from '@material-ui/icons/CheckCircle';

import SceneConfigTable from 'components/SceneCard/SceneConfigTable';

const useStyles = makeStyles(theme => ({
    deleteButton: {
        margin: theme.spacing(1),
        size: "medium",
    },
    button: {
        color: "primary",
        margin: theme.spacing(1),
        size: "medium",
        variant: "contained",
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
            <CardHeader title={scene.name} />
            <CardContent>
                {scene.devices && <SceneConfigTable devices={scene.devices} />}
            </CardContent>
            <CardActions className={classes.submitControls}>
                <Button
                    className={classes.deleteButton}
                    aria-label="Delete"
                    color="secondary"
                    variant="contained"
                    onClick={handleDelete}
                    endIcon={<DeleteIcon />}
                >
                    Delete
                </Button>
                <Button
                    className={classes.button}
                    aria-label="Activate"
                    color="primary"
                    variant="contained"
                    onClick={handleActivate}
                    endIcon={<CheckCircleIcon />}
                >
                    Activate
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
