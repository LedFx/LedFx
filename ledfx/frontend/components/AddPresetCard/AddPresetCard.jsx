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

import { addPreset } from 'frontend/actions';

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

const AddPresetCard = ({ presets, addPreset, deviceId }) =>  {

  const [ name, setName ] = useState('')
  const classes = useStyles()

  if (!presets) return null

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
              onClick = {() => addPreset(name, deviceId)}
            >
              Save
            </Button>
          </CardActions>
        </CardContent>
      </Card>
    );
}

const validateInput = (input, presets) => {
  if(!presets || !presets.customPresets || !presets.defaultPresets) return false
  const used = Object.keys(presets.customPresets).concat(Object.keys(presets.defaultPresets))
  return used.includes(input) || input === ""
}

const mapStateToProps = state => ({ 
  presets: state.presets
})

const mapDispatchToProps = (dispatch) => ({
  addPreset: (presetName, deviceId) => dispatch(addPreset(presetName, deviceId))
})

export default connect(mapStateToProps, mapDispatchToProps)(AddPresetCard);