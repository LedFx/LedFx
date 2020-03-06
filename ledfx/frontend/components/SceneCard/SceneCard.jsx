import React from 'react';
import PropTypes from 'prop-types';
import { connect } from 'react-redux'
import { withStyles } from '@material-ui/core/styles';
import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import CardActions from '@material-ui/core/CardActions';
import Button from '@material-ui/core/Button';
import red from '@material-ui/core/colors/red';
import Typography from "@material-ui/core/Typography";

import SceneConfigTable from "frontend/components/SceneCard/SceneConfigTable";

import { activateScene, deleteScene } from 'frontend/actions';

const styles = theme => ({ 
  deleteButton: {
    color: theme.palette.getContrastText(red[500]),
    backgroundColor: red[500],
    '&:hover': {
      backgroundColor: red[700],
    },
    margin: theme.spacing.unit,
    float: "right"
  },
  button: {
    margin: theme.spacing.unit,
    float: "right"
  },
  submitControls: {
    margin: theme.spacing.unit,
    display: "block",
    width: "100%"
  },

});

class SceneCard extends React.Component {

  render() {
    const { classes, scene, activateScene, deleteScene } = this.props;

    return (
      <Card>
        <CardContent>
          <Typography variant="h5" color="inherit" className={classes.header}>
            { scene.name }
          </Typography>
          { scene.devices && <SceneConfigTable devices ={ scene.devices }/> }
        </CardContent>
        <CardActions className={classes.submitControls}>
            <Button
              className={classes.button}
              color="primary"
              size="small"
              aria-label="Activate"
              variant = "contained"
              onClick={() => activateScene(scene.id)}
            >
              Activate
            </Button>
            <Button
              className={classes.deleteButton}
              color="red"
              size="small"
              aria-label="Delete"
              variant = "contained"
              onClick={() => deleteScene(scene.id)}
            >
              Delete
            </Button> 
          </CardActions>
      </Card>
    );
  }
}

SceneCard.propTypes = {
  classes: PropTypes.object.isRequired,
  scene: PropTypes.object.isRequired,
};

const mapDispatchToProps = (dispatch) => ({
  deleteScene: (sceneId) => dispatch(deleteScene(sceneId)),
  activateScene: (sceneId) => dispatch(activateScene(sceneId))
})

export default  connect(null , mapDispatchToProps)(withStyles(styles)(SceneCard));