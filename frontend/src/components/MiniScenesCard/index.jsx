import React from 'react';
import PropTypes from 'prop-types';
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
    size: "large",
    margin: theme.spacing(1),
    textDecoration: "none",
    "&,&:hover": {
      color: "#000000"
    }
  },
  submitControls: {
    display: "flex",
    width: "100%",
    height: "100%"
  },
  buttonGrid: {
    direction: "row",
    justify: "flex-start",
    alignItems: "baseline",
  }
}))


class MiniScenesCard extends React.Component {

    componentDidMount() {
        const classes = useStyles();
        this.props.getScenes();
    }

    render() {
        const { scenes, classes, activateScene } = this.props;

        return (
            <Card variant="outlined">
                <CardHeader title="Scenes" subheader="Easily deploy effects across multiple devices" />
                   /*link header to scenes management page*/
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
                        /*Buttons to activate each scene*/
                        <Grid container className={classes.buttonGrid}>
                            scenes.list.map(scene => (
                                <Grid key={scene.name} item>
                                    <Button key={scene.id}
                                            className={classes.sceneButton}
                                            onClick={() => activateScene(scene.id)}>
                                        {scene.name}
                                    </Button>
                                </Grid>
                            ));
                        </Grid>
                    )}
                </CardContent>
            </Card>
        );
    }
}

export default connect(
    state => ({
        scenes: state.scenes,
    }),
    { getScenes, activateScene }
)(withStyles(styles)(MiniScenesCard));