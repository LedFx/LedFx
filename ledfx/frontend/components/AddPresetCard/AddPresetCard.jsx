import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { connect } from 'react-redux'
import { makeStyles } from '@material-ui/core/styles';

import Card from '@material-ui/core/Card';
import CardContent from '@material-ui/core/CardContent';
import CardActions from '@material-ui/core/CardActions';
import TextField from '@material-ui/core/TextField';
import Button from '@material-ui/core/Button';
import Typography from "@material-ui/core/Typography";

import actions from 'frontend/actions';

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

const AddPresetCard = ({ presets, addPreset }) =>  {

  const [ name, setName ] = useState('')
  const classes = useStyles()

  console.log(actions)

  return (
      <Card>
        <CardContent>
          <Typography variant="h5" color="inherit" className={classes.header}>
            Add Preset
          </Typography>
          <Typography variant="caption text" color="inherit" className={classes.subHeader}>
            Save this effect configuration as a preset
          </Typography>
          <CardActions className = {classes.action}>
            <TextField
              error = {validateInput(name, presets)} 
              id="presetNameInput"
              label="Preset Name"
              onChange={(e) => setName(e.target.value)}
            />
            <Button
              className = {classes.button}
              color="primary"
              size="small"
              aria-label="Save"
              disabled = {validateInput(name, presets)} 
              variant = "contained"
              onClick = {() => addPreset(name)}
            >
              Save
            </Button>
          </CardActions>
        </CardContent>
      </Card>
    );
}

const validateInput = (input, presets) => (presets && Object.keys(presets).includes(input) || input === "")

const mapStateToProps = state => ({ 
  presets: state.presets
})

const mapDispatchToProps = (dispatch) => ({
  addPreset: (presetName) => dispatch(addPreset(presetName))
})

export default connect(mapStateToProps, mapDispatchToProps)(AddPresetCard);