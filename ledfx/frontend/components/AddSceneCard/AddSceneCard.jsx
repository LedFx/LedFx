import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { connect } from 'react-redux'
import { makeStyles } from '@material-ui/core/styles';

import Card from '@material-ui/core/Card';
import CardHeader from '@material-ui/core/CardHeader';
import CardContent from '@material-ui/core/CardContent';
import CardActions from '@material-ui/core/CardActions';
import TextField from '@material-ui/core/TextField';
import Button from '@material-ui/core/Button';
import Typography from "@material-ui/core/Typography";

import { addScene } from 'frontend/actions';

const useStyles = makeStyles({ 
  button: {
    display: "block",
    width: "100",
    float: "right"
  },
  action: {
    padding: "0"
  }
});

const AddSceneCard = ({ scenes, addScene }) =>  {

  const [ name, setName ] = useState('')
  const classes = useStyles()

  return (
      <Card>
        <CardHeader title="Add Scene" subheader="Save current effects of all devices as a scene" />
        <CardContent>
          <CardActions className = {classes.action}>
            <TextField
              error = {validateInput(name, scenes)} 
              id="sceneNameInput"
              label="Scene Name"
              onChange={(e) => setName(e.target.value)}
            />
            <Button
              className = {classes.button}
              color="primary"
              size="small"
              aria-label="Save"
              disabled = {validateInput(name, scenes)} 
              variant = "contained"
              onClick = {() => addScene(name)}
            >
              Save
            </Button>
          </CardActions>
        </CardContent>
        
      </Card>
    );
}

const validateInput = (input, scenes) => (Object.keys(scenes).includes(input) || input === "")

const mapStateToProps = state => ({ 
  scenes: state.scenes
})

const mapDispatchToProps = (dispatch) => ({
  addScene: (sceneName) => dispatch(addScene(sceneName))
})

export default connect(mapStateToProps, mapDispatchToProps)(AddSceneCard);