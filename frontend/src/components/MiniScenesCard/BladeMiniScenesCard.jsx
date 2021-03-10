import React, { useEffect } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { makeStyles } from '@material-ui/core/styles';
import Card from '@material-ui/core/Card';
import CardHeader from '@material-ui/core/CardHeader';
import CardContent from '@material-ui/core/CardContent';
import Button from '@material-ui/core/Button';
import Grid from '@material-ui/core/Grid';
import CircularProgress from '@material-ui/core/CircularProgress';
import { getScenes, activateScene } from 'modules/scenes';

const useStyles = makeStyles(theme => ({
    sceneButton: {
        size: 'large',
        margin: theme.spacing(1),
    },
    submitControls: {
        display: 'flex',
        flexWrap: 'wrap',
        width: '100%',
        height: '100%',
    },
}));

const BladeMiniScenesCard = () => {
    const scenes = useSelector(state => state.scenes);
    const dispatch = useDispatch()
    const classes = useStyles();

    useEffect(() => {
        getScenes();
    }, []);
    return (
        <Card>
            <CardHeader title="Scenes" subheader="Easily deploy effects across multiple devices" />
            <CardContent className={classes.submitControls}>
                {scenes.isLoading ? (
                    <Grid
                        container
                        justify="center"
                        alignContent="center"
                        className={classes.spinnerContainer}
                    >
                        <CircularProgress size={80} />
                    </Grid>
                ) : (
                        scenes.list.map(scene => (
                            <Button
                                key={scene.id}
                                variant={'text'}
                                color={'inherit'}
                                className={classes.sceneButton}
                                onClick={() => dispatch(activateScene(scene.id))}
                            >
                                {scene.name}
                            </Button>
                        ))
                    )}
            </CardContent>
        </Card>
    );
};

export default BladeMiniScenesCard;
