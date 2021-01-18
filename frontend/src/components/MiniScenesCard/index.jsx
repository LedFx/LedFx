import React from 'react';
import withStyles from '@material-ui/core/styles/withStyles';
import Card from '@material-ui/core/Card';
import CardHeader from '@material-ui/core/CardHeader';
import CardContent from '@material-ui/core/CardContent';
import Button from '@material-ui/core/Button';
import Grid from '@material-ui/core/Grid';
import CircularProgress from '@material-ui/core/CircularProgress';

const styles = theme => ({
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
});

class MiniScenesCard extends React.Component {
    render() {
        const { scenes, classes, activateScene } = this.props;

        return (
            <Card>
                <CardHeader
                    title="Scenes"
                    subheader="Easily deploy effects across multiple devices"
                />
                {/*link header to scenes management page*/}
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
                                onClick={() => {
                                    activateScene(scene.id);
                                    window.location = window.location.href;
                                }}
                            >
                                {scene.name}
                            </Button>
                        ))
                    )}
                </CardContent>
            </Card>
        );
    }
}

export default withStyles(styles)(MiniScenesCard);
