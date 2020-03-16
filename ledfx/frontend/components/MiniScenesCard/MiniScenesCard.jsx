import React, { useEffect } from 'react';
import PropTypes from 'prop-types';
import { connect } from 'react-redux'
import { makeStyles } from '@material-ui/core/styles';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import CardHeader from '@material-ui/core/CardHeader';
import Button from '@material-ui/core/Button';
import Grid from "@material-ui/core/Grid";

import { activateScene, getScenes } from 'frontend/actions';
import { mapIncludeKey } from 'frontend/utils/helpers';

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

const MiniScenesCard = ({ scenes, activateScene, getScenes }) => {

  const classes = useStyles()
  useEffect(getScenes, [])
    
  if (!scenes) {
    return
  }

  return (
      <Card variant="outlined">
        <CardHeader title="Scenes" subheader="Easily deploy effects across multiple devices" />
           {/*link header to scenes management page*/}
        <CardContent className={classes.submitControls}>
          {/*Buttons to activate each scene*/}
          <Grid container className={classes.buttonGrid}>
            {
              mapIncludeKey(scenes).map(scene => {
                return (
                  <Grid item>
                    <Button
                      key={scene.id}
                      className={classes.sceneButton}
                      onClick={() => activateScene(scene.id)}
                    >
                      {scene.name}
                    </Button>
                  </Grid>
                );
              })
            }
          </Grid>
        </CardContent>
      </Card>
    );
}


const mapStateToProps = state => ({ 
  scenes: state.scenes 
})

const mapDispatchToProps = (dispatch) => ({
  activateScene: (sceneId) => dispatch(activateScene(sceneId)),
  getScenes: () => dispatch(getScenes())
})

export default connect(mapStateToProps, mapDispatchToProps)(MiniScenesCard);