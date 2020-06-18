import React from 'react';
import PropTypes from 'prop-types';
import { makeStyles } from '@material-ui/core/styles';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import CardActions from '@material-ui/core/CardActions';
import Button from '@material-ui/core/Button';
import red from '@material-ui/core/colors/red';

import PresetConfigTable from 'components/PresetCard/PresetConfigTable';

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

export default function PresetCard({ preset, activatePreset, deletePreset }) {
    const classes = useStyles();

    const handleActivate = () => {
        activatePreset(preset.id);
    };

    const handleDelete = () => {
        deletePreset(preset.id);
    };

    return (
        <Card>
            <CardContent>
                <h3>{preset.name}</h3>
                {preset.devices && <PresetConfigTable devices={preset.devices} />}
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

PresetCard.propTypes = {
    preset: PropTypes.object.isRequired,
    deletePreset: PropTypes.func.isRequired,
    activatePreset: PropTypes.func.isRequired,
};
