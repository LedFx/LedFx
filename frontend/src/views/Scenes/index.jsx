import React from 'react';
import { connect } from 'react-redux';

import withStyles from '@material-ui/core/styles/withStyles';
import Grid from '@material-ui/core/Grid';
import CircularProgress from '@material-ui/core/CircularProgress';

import ScenesCard from 'components/SceneCard';
import AddSceneCard from 'components/AddSceneCard';
import { getScenes, addScene, activateScene, deleteScene } from 'modules/scenes';

const styles = theme => ({
    cardResponsive: {
        width: '100%',
        overflowX: 'auto',
    },
    button: {
        position: 'absolute',
        bottom: theme.spacing(2),
        right: theme.spacing(2),
    },
    dialogButton: {
        float: 'right',
    },
    spinnerContainer: {
        height: '10rem',
    },
});

class ScenesView extends React.Component {
    componentDidMount() {
        this.props.getScenes();
    }

    handleAddScene = name => {
        const { addScene } = this.props;
        addScene(name);
    };

    render() {
        const { scenes, classes, deleteScene, activateScene } = this.props;

        return (
            <Grid container direction="row" spacing={4}>
                <Grid item xs={12}>
                    <AddSceneCard scenes={scenes} addScene={this.handleAddScene} />
                </Grid>
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
                        <Grid key={scene.name} item xs={12} md={6}>
                            <ScenesCard
                                key={scene.id}
                                scene={scene}
                                deleteScene={deleteScene}
                                activateScene={activateScene}
                            />
                        </Grid>
                    ))
                )}
            </Grid>
        );
    }
}

export default connect(
    state => ({
        scenes: state.scenes,
    }),
    { getScenes, addScene, activateScene, deleteScene }
)(withStyles(styles)(ScenesView));
